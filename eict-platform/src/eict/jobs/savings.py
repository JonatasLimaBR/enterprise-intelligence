"""Oportunidades de economia e medição das iniciativas, no fim do correlate, no máximo 1×/hora.

Tudo é calculado antes de qualquer escrita; uma falha no meio preserva os read models anteriores.
O ciclo nunca escreve em `ops.savings_initiatives` — a decisão é da pessoa, no console.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from eict.adapters import billing, lineage, savings_config, store
from eict.adapters import capabilities as capability_probe
from eict.config import Settings
from eict.domain import problems
from eict.domain import savings as sv
from eict.domain.impact import Edge
from eict.domain.models import SUCCESS_STATE
from eict.domain.producers import normalize

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = timedelta(hours=1)
HORIZON = timedelta(days=90)
MONEY = Decimal("0.0001")
RATIO = Decimal("0.000001")
DEFAULT_CURRENCY = "USD"
PRICE_BASIS = "lista"


def policy_path(settings: Settings) -> Path:
    if settings.savings_policy:
        return Path(settings.savings_policy)
    return Path(__file__).resolve().parents[3] / "finops" / "savings.yaml"


def _money(value: Decimal | None, quantum: Decimal = MONEY) -> Decimal | None:
    return value.quantize(quantum) if value is not None else None


@dataclass(frozen=True)
class SavingsInputs:
    policy: sv.Policy
    config_error: str
    incidents: list[dict]
    run_costs: list[dict]
    causes: dict[str, tuple[str, float]]
    runs: list[sv.RunRecord]
    first_seen: dict[str, datetime]
    job_names: dict[str, str]
    schedules: list[sv.JobSchedule] | None
    job_daily: dict[str, dict[date, tuple[Decimal, int]]]
    warehouse_hours: list[sv.WarehouseHour]
    busy: frozenset[tuple[str, datetime]] | None
    owners: dict[str, tuple[str, bool]]
    producer_assets: dict[str, tuple[str, ...]]
    edges: tuple[Edge, ...]
    platform_warehouse_id: str
    initiatives: list[dict]
    billing_available: bool = True


def days_observed(first_seen: dict[str, datetime], now: datetime, window_days: int) -> dict[str, int]:
    return {
        job_id: max(1, min(window_days, (now - inicio).days or 1)) for job_id, inicio in first_seen.items()
    }


def runs_in_window(runs: list[sv.RunRecord], now: datetime, window_days: int) -> dict[str, int]:
    inicio = now - timedelta(days=window_days)
    contagem: dict[str, int] = {}
    for run in runs:
        if run.start_time >= inicio:
            contagem[run.job_id] = contagem.get(run.job_id, 0) + 1
    return contagem


def job_costs_window(
    job_daily: dict[str, dict[date, tuple[Decimal, int]]], now: datetime, window_days: int
) -> tuple[dict[str, tuple[Decimal, int]], dict[str, int]]:
    """(custo e runs na janela por job, dias observados por job) a partir do custo diário."""
    inicio = (now - timedelta(days=window_days)).date()
    custos, dias = {}, {}
    for job_id, por_dia in job_daily.items():
        janela = {dia: valor for dia, valor in por_dia.items() if dia >= inicio}
        total = sum((valor for valor, _ in janela.values()), Decimal("0"))
        custos[job_id] = (total, sum(n for _, n in janela.values()))
        if por_dia:
            dias[job_id] = max(1, min(window_days, (now.date() - min(por_dia)).days + 1))
    return custos, dias


def idle_daily(hours: list[sv.WarehouseHour], busy: frozenset, warehouse_id: str) -> dict[date, Decimal]:
    diario: dict[date, Decimal] = {}
    for item in sv.idle_hours([hora for hora in hours if hora.warehouse_id == warehouse_id], busy):
        diario[item.hour.date()] = diario.get(item.hour.date(), Decimal("0")) + item.cost
    return diario


def detect_all(inputs: SavingsInputs, now: datetime) -> list[sv.DetectorOutcome]:
    politica = inputs.policy
    janela = politica.estimate_window_days
    dias = days_observed(inputs.first_seen, now, janela)
    if inputs.billing_available:
        falhas = sv.detect_failed(inputs.runs, dias, inputs.job_names, now, politica)
    else:
        falhas = sv.not_evaluated(sv.FALHA, "billing indisponível")
    falhados = frozenset(run_id for item in falhas.opportunities for run_id in item.evidence)
    regressao = sv.detect_regression(
        inputs.incidents, inputs.run_costs, inputs.causes, runs_in_window(inputs.runs, now, janela), dias,
        inputs.job_names, falhados, politica,
    )
    if inputs.schedules is None:
        schedule = sv.not_evaluated(sv.SCHEDULE, "SDK de jobs indisponível para ler os schedules")
    else:
        custos, dias_job = job_costs_window(inputs.job_daily, now, janela)
        schedule = sv.detect_schedule(inputs.schedules, custos, dias_job, now, politica)
    ocioso = sv.detect_idle_warehouse(inputs.warehouse_hours, inputs.busy, now, politica)
    return [regressao, falhas, schedule, ocioso]


def enrich(opportunity: sv.Opportunity, inputs: SavingsInputs, now: datetime) -> sv.Opportunity:
    if opportunity.source == sv.OCIOSO:
        plataforma = opportunity.subject == inputs.platform_warehouse_id
        motivo = "o console e as regras de qualidade usam este warehouse" if plataforma else (
            "consumidores do warehouse não mapeados"
        )
        return replace(opportunity, risk=sv.MEDIO, risk_reason=motivo)
    nivel, motivo = sv.risk(opportunity.subject_name, inputs.producer_assets, inputs.edges, now)
    dono, alocado = inputs.owners.get(opportunity.job_id, ("", False))
    return replace(
        opportunity, risk=nivel, risk_reason=motivo, owner=dono,
        note="" if alocado else "atribuir dono primeiro",
    )


def realizations(inputs: SavingsInputs, now: datetime) -> list[sv.Realization]:
    resultado = []
    runs_por_job: dict[str, list[sv.RunRecord]] = {}
    for run in inputs.runs:
        runs_por_job.setdefault(run.job_id, []).append(run)
    for iniciativa in inputs.initiatives:
        if iniciativa.get("state") != sv.IMPLEMENTADA:
            continue
        fonte = iniciativa["source"]
        if fonte == sv.OCIOSO and inputs.busy is None:
            resultado.append(
                sv.Realization(iniciativa["initiative_id"], sv.AMOSTRA_INSUFICIENTE, sv.POR_DIA,
                               reason="system.query.history indisponível: ociosidade não medida")
            )
            continue
        if fonte == sv.OCIOSO:
            diario = idle_daily(inputs.warehouse_hours, inputs.busy, iniciativa["subject"])
        else:
            por_dia = inputs.job_daily.get(iniciativa.get("job_id") or "", {})
            diario = {dia: valor for dia, (valor, _) in por_dia.items()}
        nome = inputs.job_names.get(iniciativa.get("job_id") or "", "")
        ativos = set(inputs.producer_assets.get(normalize(nome), ()))
        colaterais = [item for item in inputs.incidents if item.get("subject") in ativos]
        medida = sv.measure(
            iniciativa, runs_por_job.get(iniciativa.get("job_id") or "", []), diario, colaterais, now, inputs.policy
        )
        if medida is not None:
            resultado.append(medida)
    return resultado


def build_rows(inputs: SavingsInputs, now: datetime) -> dict[str, list[dict]]:
    """Linhas dos três read models do ciclo, puro. Chave = nome da tabela em `ops`."""
    politica = inputs.policy
    detectores = detect_all(inputs, now)
    medidas = realizations(inputs, now)
    estados = {item.initiative_id: item.state for item in medidas}
    for item in inputs.initiatives:
        if item.get("state") == sv.IMPLEMENTADA and item["initiative_id"] not in estados:
            estados[item["initiative_id"]] = sv.EM_MEDICAO
    oportunidades = [item for detector in detectores for item in detector.opportunities]
    oportunidades = sv.link_initiatives(sv.assign_groups(oportunidades, now), inputs.initiatives, estados)
    oportunidades = [enrich(item, inputs, now) for item in oportunidades]
    comum = {"currency": DEFAULT_CURRENCY, "price_basis": PRICE_BASIS, "policy_version": politica.policy_version,
             "computed_at": now}
    linhas_oportunidade = [
        {
            **comum,
            "opportunity_id": item.opportunity_id,
            "source": item.source,
            "subject": item.subject,
            "subject_name": item.subject_name,
            "job_id": item.job_id,
            "occurrence": item.occurrence,
            "group_id": item.group_id,
            "status": item.status,
            "initiative_id": item.initiative_id,
            "contained_in": item.contained_in,
            "counted": item.counted,
            "estimate_usd": _money(item.estimate.value),
            "estimate_low": _money(item.estimate.low),
            "estimate_high": _money(item.estimate.high),
            "n": item.estimate.n,
            "short_history": item.estimate.short_history,
            "unit": item.unit,
            "formula": item.formula,
            "confidence": item.confidence,
            "confidence_label": item.confidence_label,
            "risk": item.risk,
            "risk_reason": item.risk_reason,
            "owner": item.owner,
            "note": item.note,
            "hypothesis_code": item.hypothesis_code,
            "evidence": list(item.evidence),
            "recommendation": item.recommendation,
            "period_label": sv.month_label(now),
        }
        for item in oportunidades
    ]
    linhas_detector = [
        {
            **comum,
            "source": item.source,
            "status": item.status,
            "reason": item.reason,
            "evaluated_count": item.evaluated,
            "opportunity_count": len(item.opportunities),
            "below_threshold": item.below_threshold,
            "below_threshold_usd": _money(item.below_threshold_usd),
            "config_error": inputs.config_error,
        }
        for item in detectores
    ]
    linhas_medida = [
        {
            **comum,
            "initiative_id": item.initiative_id,
            "state": item.state,
            "unit": item.unit,
            "baseline_median": _money(item.baseline_median, RATIO),
            "after_median": _money(item.after_median, RATIO),
            "n_before": item.n_before,
            "n_after": item.n_after,
            "monthly_volume": item.monthly_volume,
            "gross_usd": _money(item.gross_usd),
            "net_usd": _money(item.net_usd),
            "side_effect_incidents": list(item.side_effect_incidents),
            "reason": item.reason,
        }
        for item in medidas
    ]
    return {
        "savings_opportunities": linhas_oportunidade,
        "savings_detectors": linhas_detector,
        "savings_realization": linhas_medida,
    }


def top_causes(hypotheses_by_incident: dict[str, list[dict]]) -> dict[str, tuple[str, float]]:
    """Hipótese nº 1 não descartada de cada incidente, com a confiança."""
    causas = {}
    for incident_id, hipoteses in hypotheses_by_incident.items():
        codigo = problems.top_cause(hipoteses)
        escolhida = next((item for item in hipoteses if item.get("code") == codigo), None)
        if escolhida is not None:
            causas[incident_id] = (codigo, float(escolhida.get("confidence") or 0.0))
    return causas


def last_computed(spark: Any, settings: Settings) -> datetime | None:
    linhas = store.query(
        spark, f"SELECT MAX(computed_at) AS computed_at FROM {settings.table('ops', 'savings_detectors')}"
    )
    return linhas[0].get("computed_at") if linhas else None


def load_schedules() -> list[sv.JobSchedule] | None:
    try:
        from databricks.sdk import WorkspaceClient

        from eict.adapters.databricks_jobs import job_schedules

        return [sv.JobSchedule(*item) for item in job_schedules(WorkspaceClient())]
    except Exception as exc:
        logger.warning("schedules indisponíveis: %s", exc)
        return None


def load_inputs(spark: Any, settings: Settings, now: datetime) -> SavingsInputs:
    from eict.adapters.contract_loader import load_directory as load_contracts
    from eict.jobs.correlate import billing_facts, reviewed_hypotheses
    from eict.jobs.finops import workspace_scope
    from eict.jobs.quality import contracts_dir

    politica, erro = savings_config.load(policy_path(settings))
    inicio = now - HORIZON
    capacidades = {
        row["capability"]: row["status"]
        for row in store.query(spark, f"SELECT capability, status FROM {settings.table('ops', 'capabilities')}")
    }
    billing_ok = capacidades.get(capability_probe.BILLING_USAGE) == capability_probe.AVAILABLE
    historico_ok = capacidades.get(capability_probe.QUERY_HISTORY) == capability_probe.AVAILABLE
    features = store.query(
        spark,
        f"SELECT run_id, job_id, start_time, result_state, input_rows FROM {settings.table('gold', 'run_features')}",
    )
    primeiro: dict[str, datetime] = {}
    for row in features:
        atual = primeiro.get(row["job_id"])
        if atual is None or row["start_time"] < atual:
            primeiro[row["job_id"]] = row["start_time"]
    recentes = [row for row in features if row["start_time"] >= inicio]
    custos = billing_facts(spark, [row["run_id"] for row in recentes], billing_ok)
    runs = [
        sv.RunRecord(
            row["run_id"], row["job_id"], row["start_time"], row["result_state"] == SUCCESS_STATE,
            billing.to_decimal(custos[row["run_id"]].list_cost_usd) if row["run_id"] in custos else None,
            row.get("input_rows"),
        )
        for row in recentes
    ]
    nomes = {
        str(row["job_id"]): row["name"]
        for row in store.query(spark, f"SELECT job_id, name FROM {settings.table('ops', 'monitored_jobs')}")
        if row.get("name")
    }
    iniciativas = store.query(spark, f"SELECT * FROM {settings.table('ops', 'savings_initiatives')}")
    schedules = load_schedules()
    for item in schedules or []:
        nomes.setdefault(item.job_id, item.name)
    workspace_id, _ = workspace_scope()
    jobs_diarios = sorted(
        {
            item.job_id for item in schedules or []
            if not item.paused and sv.is_non_prod(item.name, politica.non_prod_targets)
        }
        | {item["job_id"] for item in iniciativas if item.get("source") == sv.SCHEDULE and item.get("job_id")}
    )
    job_daily: dict[str, dict[date, tuple[Decimal, int]]] = {}
    if billing_ok:
        for row in billing.job_daily_costs(spark, jobs_diarios, inicio, now, workspace_id):
            job_daily.setdefault(row["job_id"], {})[row["day"]] = (billing.to_decimal(row["cost"]), int(row["runs"]))
    horas = []
    busy = None
    if billing_ok and historico_ok:
        from eict.adapters import query_history

        horas = [
            sv.WarehouseHour(row["warehouse_id"], store.ensure_utc(row["hour"]), billing.to_decimal(row["cost"]))
            for row in billing.warehouse_hours(spark, inicio, now, workspace_id)
        ]
        busy = query_history.busy_hours(spark, inicio, now)
    donos = {}
    for row in store.query(
        spark,
        f"SELECT resource_id, owner, category FROM {settings.table('ops', 'cost_allocation')} "
        f"WHERE resource_kind = 'job' AND period_label = '{sv.month_label(now)}'",
    ):
        donos[row["resource_id"]] = (row.get("owner") or "", row.get("category") != "nao_alocado")
    produtores: dict[str, list[str]] = {}
    for contrato in load_contracts(contracts_dir(settings)).active:
        produtores.setdefault(normalize(contrato.producer), []).append(contrato.asset)
    return SavingsInputs(
        policy=politica,
        config_error=erro,
        incidents=store.query(spark, f"SELECT * FROM {settings.table('ops', 'incidents')}"),
        run_costs=store.query(spark, f"SELECT * FROM {settings.table('ops', 'run_cost')}"),
        causes=top_causes(reviewed_hypotheses(spark, settings)),
        runs=runs,
        first_seen=primeiro,
        job_names=nomes,
        schedules=schedules,
        job_daily=job_daily,
        warehouse_hours=horas,
        busy=busy,
        owners=donos,
        producer_assets={chave: tuple(sorted(ativos)) for chave, ativos in produtores.items()},
        edges=lineage.load_graph(spark, settings),
        platform_warehouse_id=settings.platform_warehouse_id,
        initiatives=iniciativas,
        billing_available=billing_ok,
    )


def refresh(spark: Any, settings: Settings, now: datetime, force: bool = False) -> dict[str, int]:
    if not force:
        ultimo = last_computed(spark, settings)
        if ultimo is not None and now - ultimo < REFRESH_INTERVAL:
            logger.info("economia recente; billing e SDK não consultados neste ciclo")
            return {}
    linhas = build_rows(load_inputs(spark, settings, now), now)
    return {tabela: store.replace_rows(spark, settings.table("ops", tabela), rows) for tabela, rows in linhas.items()}
