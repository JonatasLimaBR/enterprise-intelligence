"""Showback no fim do correlate: alocação, reconciliação e custo por unidade, no máximo 1×/hora.

Tudo é calculado antes de qualquer escrita. Se uma consulta ao billing falhar, nada é gravado e o
console segue com o showback anterior e o seu `computed_at` — nunca metade de um período.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from eict.adapters import allocation_loader, billing, store
from eict.config import Settings
from eict.domain import allocation, unit_costs
from eict.domain.allocation import (
    APP,
    JOB,
    PIPELINE,
    PRICE_BASIS,
    WAREHOUSE,
    Allocation,
    ContractOwner,
    Period,
    RuleSet,
    UsageLine,
)
from eict.domain.models import SUCCESS_STATE

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = timedelta(hours=1)
DEFAULT_CURRENCY = "USD"
MONEY = Decimal("0.0001")
MAX_RUNS_PER_JOB = 2000


def allocation_dir(settings: Settings) -> Path:
    if settings.allocation_dir:
        return Path(settings.allocation_dir)
    return Path(__file__).resolve().parents[3] / "allocation"


def money(value: Decimal | None) -> Decimal | None:
    return value.quantize(MONEY) if value is not None else None


def is_recent(last_computed: datetime | None, now: datetime) -> bool:
    return last_computed is not None and now - last_computed < REFRESH_INTERVAL


def to_lines(records: list[dict], job_names: dict[str, str]) -> list[UsageLine]:
    """Linha de billing → recurso identificado. Ordem: job, pipeline, warehouse, app, nenhum."""
    linhas = []
    for record in records:
        dbus = billing.to_decimal(record.get("dbus"))
        custo = billing.to_decimal(record.get("cost"))
        origem = record.get("origin_product") or ""
        if record.get("job_id"):
            job_id = str(record["job_id"])
            nome = job_names.get(job_id) or record.get("job_name") or ""
            linhas.append(UsageLine(JOB, job_id, nome, record.get("job_run_id") or "", origem, dbus, custo))
        elif record.get("dlt_pipeline_id"):
            pid = str(record["dlt_pipeline_id"])
            linhas.append(UsageLine(PIPELINE, pid, pid, "", origem, dbus, custo))
        elif record.get("warehouse_id"):
            wid = str(record["warehouse_id"])
            linhas.append(UsageLine(WAREHOUSE, wid, wid, "", origem, dbus, custo))
        elif record.get("app_id") or record.get("app_name"):
            linhas.append(
                UsageLine(APP, str(record.get("app_id") or record["app_name"]), record.get("app_name") or "",
                          "", origem, dbus, custo)
            )
        else:
            linhas.append(UsageLine("", "", "", "", origem, dbus, custo))
    return linhas


def contract_pairs(contracts: list[Any]) -> list[tuple[str, ContractOwner]]:
    return [
        (contract.producer, ContractOwner(contract.contract_id, contract.owner, contract.asset))
        for contract in contracts
    ]


def run_costs(allocations: list[Allocation]) -> tuple[list[unit_costs.RunCost], dict[str, str]]:
    """Custo por (job, run) e o dono de cada job, a partir das linhas já alocadas."""
    custos: dict[tuple[str, str], Decimal] = {}
    nomes: dict[str, str] = {}
    donos: dict[str, str] = {}
    for item in allocations:
        linha = item.line
        if linha.resource_kind != JOB or not linha.run_id:
            continue
        chave = (linha.resource_id, linha.run_id)
        custos[chave] = custos.get(chave, Decimal("0")) + linha.cost
        nomes[linha.resource_id] = linha.resource_name
        donos.setdefault(linha.resource_id, item.owner)
    runs = [
        unit_costs.RunCost(job_id, nomes[job_id], run_id, custo)
        for (job_id, run_id), custo in sorted(custos.items())
    ]
    return runs, donos


@dataclass(frozen=True)
class PeriodInput:
    period: Period
    records: list[dict]
    total: billing.PeriodTotal


def period_rows(
    entrada: PeriodInput,
    rules: RuleSet,
    job_names: dict[str, str],
    succeeded: dict[str, bool | None],
    input_rows: dict[str, int | None],
    incidents: list[dict],
    run_cost_rows: list[dict],
    cycle_job_names: frozenset[str],
    scope: str,
    now: datetime,
) -> dict[str, list[dict]]:
    periodo = entrada.period
    alocacoes = allocation.allocate(to_lines(entrada.records, job_names), rules)
    somas = allocation.totals(alocacoes)
    conciliacao = allocation.reconcile(entrada.total.total_cost, somas, entrada.total.currencies or (DEFAULT_CURRENCY,))
    moeda = ",".join(conciliacao.currencies) or DEFAULT_CURRENCY
    base = {
        "period_label": periodo.label,
        "period_start": periodo.start,
        "period_end": periodo.end,
        "currency": moeda,
        "price_basis": PRICE_BASIS,
        "computed_at": now,
    }
    alocacao = [
        {**base, **row, "dbus": float(row["dbus"]), "cost": money(row["cost"])}
        for row in allocation.allocation_rows(alocacoes)
    ]
    reconciliacao = [
        {
            **base,
            "period_status": periodo.status_label,
            "watermark": entrada.total.watermark if periodo.current else None,
            "total_billing": money(conciliacao.total_billing),
            "allocated": money(somas.allocated),
            "platform_pool": money(somas.platform_pool),
            "unallocated": money(somas.unallocated),
            "difference": money(conciliacao.difference),
            "tolerance": money(conciliacao.tolerance),
            "reconciled": conciliacao.reconciled,
            "reason": conciliacao.reason,
            "unpriced_dbus": float(entrada.total.unpriced_dbus),
            "allocated_share": somas.allocated_share,
            "scope": scope,
        }
    ]
    runs, donos = run_costs(alocacoes)
    unidades = unit_costs.units_for_jobs(runs, donos, succeeded, input_rows, cycle_job_names)
    por_incidente, _ = unit_costs.per_incident(incidents, run_cost_rows, periodo.start, periodo.end)
    unidades.append(por_incidente)
    unidades_rows = [
        {
            **base,
            "unit": item.unit,
            "subject": item.subject,
            "owner": item.owner,
            "formula": item.formula,
            "median": money(item.median),
            "mean": money(item.mean),
            "n": item.n,
            "status": item.status,
        }
        for item in unidades
    ]
    return {"cost_allocation": alocacao, "cost_reconciliation": reconciliacao, "cost_units": unidades_rows}


def build_rows(
    entradas: list[PeriodInput],
    rules: RuleSet,
    rule_rows: list[dict],
    job_names: dict[str, str],
    succeeded: dict[str, bool | None],
    input_rows: dict[str, int | None],
    incidents: list[dict],
    run_cost_rows: list[dict],
    cycle_job_names: frozenset[str],
    scope: str,
    now: datetime,
) -> dict[str, list[dict]]:
    """Todas as linhas dos quatro read models, puro. Chave = nome da tabela em `ops`."""
    linhas: dict[str, list[dict]] = {
        "allocation_rules": rule_rows,
        "cost_allocation": [],
        "cost_reconciliation": [],
        "cost_units": [],
    }
    for entrada in entradas:
        for tabela, rows in period_rows(
            entrada, rules, job_names, succeeded, input_rows, incidents, run_cost_rows, cycle_job_names, scope, now
        ).items():
            linhas[tabela].extend(rows)
    return linhas


def workspace_scope() -> tuple[str, str]:
    """(workspace_id, rótulo). Sem id, o escopo é a conta — dito no rótulo."""
    try:
        from databricks.sdk import WorkspaceClient

        workspace_id = str(WorkspaceClient().get_workspace_id())
    except Exception as exc:
        logger.warning("workspace_id indisponível, showback no escopo da conta: %s", exc)
        return "", "conta"
    if not workspace_id.isdigit():
        return "", "conta"
    return workspace_id, f"workspace {workspace_id}"


def sdk_run_results(job_ids: list[str], since: datetime) -> dict[str, bool]:
    if not job_ids:
        return {}
    try:
        from databricks.sdk import WorkspaceClient

        from eict.adapters.databricks_jobs import run_results

        client = WorkspaceClient()
        return run_results(CappedJobs(client), job_ids, int(since.timestamp() * 1000))
    except Exception as exc:
        logger.warning("estado dos runs fora das features indisponível: %s", exc)
        return {}


class CappedJobs:
    """Limita a paginação de `list_runs`: o ciclo a cada 5 min soma milhares de runs no mês."""

    def __init__(self, client: Any) -> None:
        self.jobs = self
        self._client = client

    def list_runs(self, **kwargs: Any):
        return itertools.islice(self._client.jobs.list_runs(**kwargs), MAX_RUNS_PER_JOB)


def last_computed(spark: Any, settings: Settings) -> datetime | None:
    linhas = store.query(
        spark, f"SELECT MAX(computed_at) AS computed_at FROM {settings.table('ops', 'cost_reconciliation')}"
    )
    return linhas[0].get("computed_at") if linhas else None


def refresh(spark: Any, settings: Settings, now: datetime, force: bool = False) -> dict[str, int]:
    from eict.adapters.contract_loader import load_directory as load_contracts
    from eict.jobs.quality import contracts_dir

    if not force and is_recent(last_computed(spark, settings), now):
        logger.info("showback recente; billing não consultado neste ciclo")
        return {}
    carga = allocation_loader.load_directory(allocation_dir(settings))
    contratos = load_contracts(contracts_dir(settings)).active
    regras = allocation.build_rules(
        carga.domains,
        carga.platform,
        contract_pairs(list(contratos)),
        settings.pipeline_id,
        settings.platform_warehouse_id,
    )
    workspace_id, escopo = workspace_scope()
    entradas = [
        PeriodInput(
            periodo,
            billing.usage_records(spark, periodo.start, periodo.end, workspace_id),
            billing.period_total(spark, periodo.start, periodo.end, workspace_id),
        )
        for periodo in allocation.periods(now)
    ]
    nomes = {
        str(row["job_id"]): row["name"]
        for row in store.query(spark, f"SELECT job_id, name FROM {settings.table('ops', 'monitored_jobs')}")
        if row.get("name")
    }
    features = store.query(
        spark, f"SELECT run_id, result_state, input_rows FROM {settings.table('gold', 'run_features')}"
    )
    sucesso: dict[str, bool | None] = {row["run_id"]: row["result_state"] == SUCCESS_STATE for row in features}
    linhas_por_run = {row["run_id"]: row.get("input_rows") for row in features}
    sem_estado = sorted(
        {
            str(record["job_id"])
            for entrada in entradas
            for record in entrada.records
            if record.get("job_id") and record.get("job_run_id") and record["job_run_id"] not in sucesso
        }
    )
    sucesso.update(sdk_run_results(sem_estado, entradas[0].period.start))
    incidentes = store.query(spark, f"SELECT incident_id, detected_at FROM {settings.table('ops', 'incidents')}")
    custos_de_run = store.query(
        spark, f"SELECT incident_id, status, incremental_cost_usd FROM {settings.table('ops', 'run_cost')}"
    )
    ciclo = frozenset({allocation.normalize(unit_costs.CYCLE_JOB)})
    linhas = build_rows(
        entradas,
        regras,
        allocation.rule_rows(carga.domains, carga.platform, regras, carga.errors, now),
        nomes,
        sucesso,
        linhas_por_run,
        incidentes,
        custos_de_run,
        ciclo,
        escopo,
        now,
    )
    return {tabela: store.replace_rows(spark, settings.table("ops", tabela), rows) for tabela, rows in linhas.items()}
