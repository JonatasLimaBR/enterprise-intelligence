"""Oportunidades de economia e a prova de que a economia aconteceu (PRD-070 F6, F7; SPEC-012).

Quatro fontes, cada uma com fórmula, confiança e risco. O ciclo propõe; uma pessoa aprova ou
descarta; o ciclo mede depois da implementação, por unidade, contra uma janela comparável.
Economia potencial não é economia realizada: só `realizada` entra no KPI.

Fonte que não pôde ser lida é "não avaliado", nunca zero. O que fica abaixo do limiar é contado,
nunca descartado em silêncio.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from eict.domain.impact import Edge, traverse
from eict.domain.models import stable_id
from eict.domain.producers import normalize

REGRESSAO = "regressao_custo"
FALHA = "execucao_falhada"
SCHEDULE = "schedule_fora_prod"
OCIOSO = "warehouse_ocioso"
SOURCES = (REGRESSAO, FALHA, SCHEDULE, OCIOSO)

AVALIADO = "avaliado"
NAO_AVALIADO = "nao_avaliado"

IDENTIFICADA = "identificada"
EM_INICIATIVA = "em_iniciativa"

APROVADA = "aprovada"
IMPLEMENTADA = "implementada"
DESCARTADA = "descartada"

EM_MEDICAO = "em_medicao"
REALIZADA = "realizada"
NAO_REALIZADA = "nao_realizada"
AMOSTRA_INSUFICIENTE = "amostra_insuficiente"
EXPIRADA = "expirada"
EFEITO_COLATERAL = "realizada_com_efeito_colateral"
TERMINAL = frozenset({REALIZADA, NAO_REALIZADA, EXPIRADA, EFEITO_COLATERAL})

ALTO = "alto"
MEDIO = "medio"
BAIXO = "baixo"

REGRESSION_TYPES = frozenset({"runtime_regression", "cost_regression"})
SIDE_EFFECT_TYPES = frozenset({"contract_violation", "quality_engine_failure", "sla_risk"})
ACTIVE_INCIDENT_STATES = frozenset({"detected", "triaged", "investigating", "mitigating", "monitoring"})

MILLION = Decimal("1000000")
ZERO = Decimal("0")

FORMULAS = {
    REGRESSAO: "mediana do custo incremental por run do incidente × runs do job em 30 dias",
    FALHA: "Σ custo dos runs com falha nos últimos 30 dias",
    SCHEDULE: "custo do job nos últimos 30 dias (schedule ativo em target não-prod)",
    OCIOSO: "Σ custo das horas faturadas do warehouse sem nenhuma consulta nos últimos 30 dias",
}
RECOMMENDATIONS = {
    REGRESSAO: "Corrigir a causa da regressão (ver hipótese nº 1 e o runbook do incidente); não desligar o job.",
    FALHA: "Investigar e corrigir a causa das falhas; cada run repetido paga o cluster de novo.",
    SCHEDULE: "Pausar o schedule neste target não-prod ou reduzir a frequência; rodar sob demanda.",
    OCIOSO: "Ajustar auto-stop do warehouse para o padrão de uso observado; não desligar o warehouse.",
}
CONFIDENCE_LABELS = {FALHA: "alta", SCHEDULE: "alta", OCIOSO: "media"}


class SavingsConfigError(ValueError):
    """Política inválida: a etapa roda com os defaults do código e mostra a recusa."""


@dataclass(frozen=True)
class Policy:
    policy_version: str = "savings-v1"
    threshold_usd_month: Decimal = Decimal("0.10")
    estimate_window_days: int = 30
    min_runs: int = 5
    measure_days: int = 14
    expiry_days: int = 60
    non_prod_targets: tuple[str, ...] = ("dev", "staging")


def parse_policy(payload: object) -> Policy:
    if not isinstance(payload, dict):
        raise SavingsConfigError("conteúdo não é um mapeamento")
    padrao = Policy()
    try:
        politica = Policy(
            policy_version=str(payload.get("policy_version") or padrao.policy_version),
            threshold_usd_month=Decimal(str(payload.get("threshold_usd_month", padrao.threshold_usd_month))),
            estimate_window_days=int(payload.get("estimate_window_days", padrao.estimate_window_days)),
            min_runs=int(payload.get("min_runs", padrao.min_runs)),
            measure_days=int(payload.get("measure_days", padrao.measure_days)),
            expiry_days=int(payload.get("expiry_days", padrao.expiry_days)),
            non_prod_targets=tuple(str(item) for item in payload.get("non_prod_targets", padrao.non_prod_targets)),
        )
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise SavingsConfigError(f"valor inválido: {exc}") from exc
    if politica.threshold_usd_month < 0 or min(
        politica.estimate_window_days, politica.min_runs, politica.measure_days, politica.expiry_days
    ) <= 0:
        raise SavingsConfigError("limiar negativo ou janela/mínimo não positivos")
    if politica.expiry_days < politica.measure_days:
        raise SavingsConfigError("expiry_days menor que measure_days")
    return politica


@dataclass(frozen=True)
class Estimate:
    value: Decimal
    low: Decimal
    high: Decimal
    n: int
    short_history: bool


def monthly_factor(days_observed: int, window_days: int) -> Decimal:
    if days_observed <= 0 or days_observed >= window_days:
        return Decimal(1)
    return Decimal(window_days) / Decimal(days_observed)


def projected(per_run: list[Decimal], runs: int, days_observed: int, policy: Policy) -> Estimate | None:
    """Mediana por run × runs na janela, projetada se o histórico for curto; faixa quando n < mínimo."""
    if not per_run or runs <= 0:
        return None
    fator = monthly_factor(days_observed, policy.estimate_window_days)
    curto = fator != 1
    valor = statistics.median(per_run) * runs * fator
    if len(per_run) >= policy.min_runs:
        return Estimate(valor, valor, valor, len(per_run), curto)
    return Estimate(valor, min(per_run) * runs * fator, max(per_run) * runs * fator, len(per_run), curto)


def measured(total: Decimal, n: int, days_observed: int, policy: Policy) -> Estimate:
    """Custo já medido na janela: sem faixa; só projetado se o histórico for curto."""
    fator = monthly_factor(days_observed, policy.estimate_window_days)
    valor = total * fator
    return Estimate(valor, valor, valor, n, fator != 1)


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    source: str
    subject: str
    subject_name: str
    job_id: str
    occurrence: str
    estimate: Estimate
    confidence: float | None
    confidence_label: str
    hypothesis_code: str = ""
    evidence: tuple[str, ...] = ()
    unit: str = ""
    risk: str = MEDIO
    risk_reason: str = ""
    owner: str = ""
    note: str = ""
    group_id: str = ""
    contained_in: str = ""
    counted: bool = True
    status: str = IDENTIFICADA
    initiative_id: str = ""

    @property
    def formula(self) -> str:
        return FORMULAS[self.source]

    @property
    def recommendation(self) -> str:
        return RECOMMENDATIONS[self.source]


def opportunity_id(source: str, subject: str, occurrence: str) -> str:
    return stable_id("opp", source, subject, occurrence)


@dataclass(frozen=True)
class DetectorOutcome:
    source: str
    status: str
    reason: str = ""
    evaluated: int = 0
    opportunities: tuple[Opportunity, ...] = ()
    below_threshold: int = 0
    below_threshold_usd: Decimal = ZERO


def not_evaluated(source: str, reason: str) -> DetectorOutcome:
    return DetectorOutcome(source, NAO_AVALIADO, reason)


def _outcome(source: str, evaluated: int, candidatas: list[Opportunity], policy: Policy) -> DetectorOutcome:
    acima = [item for item in candidatas if item.estimate.value >= policy.threshold_usd_month]
    abaixo = [item for item in candidatas if item.estimate.value < policy.threshold_usd_month]
    return DetectorOutcome(
        source, AVALIADO, "", evaluated, tuple(acima), len(abaixo),
        sum((item.estimate.value for item in abaixo), ZERO),
    )


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    job_id: str
    start_time: datetime
    succeeded: bool
    cost: Decimal | None = None
    input_rows: int | None = None


def month_label(now: datetime) -> str:
    return now.strftime("%Y-%m")


def detect_regression(
    incidents: list[dict],
    run_costs: list[dict],
    causes: dict[str, tuple[str, float]],
    runs_in_window: dict[str, int],
    days_observed: dict[str, int],
    job_names: dict[str, str],
    failed_run_ids: frozenset[str],
    policy: Policy,
) -> DetectorOutcome:
    """Um incidente de regressão ativo com custo incremental medido ⇒ uma oportunidade.

    Run com falha fica na fonte de falhas: aqui só entram os bem-sucedidos lentos.
    """
    ativos = [
        item for item in incidents
        if item.get("type") in REGRESSION_TYPES and item.get("state") in ACTIVE_INCIDENT_STATES
    ]
    por_incidente: dict[str, list[tuple[str, Decimal]]] = {}
    for linha in run_costs:
        valor = linha.get("incremental_cost_usd")
        if linha.get("status") != "available" or valor is None or linha.get("run_id") in failed_run_ids:
            continue
        if Decimal(str(valor)) > 0:
            por_incidente.setdefault(linha["incident_id"], []).append((linha["run_id"], Decimal(str(valor))))
    candidatas = []
    for incidente in ativos:
        job_id = str(incidente.get("job_id") or incidente.get("subject") or "")
        runs = por_incidente.get(incidente["incident_id"], [])
        estimativa = projected(
            [valor for _, valor in runs], runs_in_window.get(job_id, 0), days_observed.get(job_id, 0), policy
        )
        if estimativa is None:
            continue
        codigo, confianca = causes.get(incidente["incident_id"], ("", None))
        candidatas.append(
            Opportunity(
                opportunity_id(REGRESSAO, job_id, incidente["incident_id"]),
                REGRESSAO, job_id, job_names.get(job_id, job_id), job_id, incidente["incident_id"], estimativa,
                confianca, "hipótese nº 1" if confianca is not None else "sem hipótese",
                hypothesis_code=codigo,
                evidence=(incidente["incident_id"], *sorted(run_id for run_id, _ in runs)),
                unit="custo incremental por run",
            )
        )
    return _outcome(REGRESSAO, len(ativos), candidatas, policy)


def detect_failed(
    runs: list[RunRecord],
    days_observed: dict[str, int],
    job_names: dict[str, str],
    now: datetime,
    policy: Policy,
) -> DetectorOutcome:
    """Custo pago por runs que falharam na janela — medido, não inferido."""
    inicio = now - timedelta(days=policy.estimate_window_days)
    por_job: dict[str, list[RunRecord]] = {}
    for run in runs:
        if run.start_time >= inicio and not run.succeeded and run.cost is not None and run.cost > 0:
            por_job.setdefault(run.job_id, []).append(run)
    avaliados = {run.job_id for run in runs if run.start_time >= inicio}
    candidatas = []
    for job_id, falhas in sorted(por_job.items()):
        total = sum((run.cost for run in falhas), ZERO)
        candidatas.append(
            Opportunity(
                opportunity_id(FALHA, job_id, month_label(now)), FALHA, job_id, job_names.get(job_id, job_id),
                job_id, month_label(now), measured(total, len(falhas), days_observed.get(job_id, 0), policy),
                None, CONFIDENCE_LABELS[FALHA], evidence=tuple(sorted(run.run_id for run in falhas)),
                unit="custo de runs com falha",
            )
        )
    return _outcome(FALHA, len(avaliados), candidatas, policy)


@dataclass(frozen=True)
class JobSchedule:
    job_id: str
    name: str
    paused: bool


def is_non_prod(name: str, targets: Iterable[str]) -> bool:
    """Convenção do bundle: `[dev fulano] ` no modo development ou sufixo `-<target>`."""
    bruto = (name or "").strip().lower()
    if bruto.startswith("[dev "):
        return True
    return any(bruto.endswith(f"-{alvo.lower()}") for alvo in targets)


def detect_schedule(
    schedules: list[JobSchedule],
    job_costs: dict[str, tuple[Decimal, int]],
    days_observed: dict[str, int],
    now: datetime,
    policy: Policy,
) -> DetectorOutcome:
    candidatos = [
        item for item in schedules if not item.paused and is_non_prod(item.name, policy.non_prod_targets)
    ]
    oportunidades = []
    for job in candidatos:
        custo, runs = job_costs.get(job.job_id, (ZERO, 0))
        if custo <= 0:
            continue
        oportunidades.append(
            Opportunity(
                opportunity_id(SCHEDULE, job.job_id, month_label(now)), SCHEDULE, job.job_id, job.name, job.job_id,
                month_label(now), measured(custo, runs, days_observed.get(job.job_id, 0), policy),
                None, CONFIDENCE_LABELS[SCHEDULE], evidence=(f"schedule UNPAUSED em {job.name}",),
                unit="custo mensal do job",
            )
        )
    return _outcome(SCHEDULE, len(schedules), oportunidades, policy)


@dataclass(frozen=True)
class WarehouseHour:
    warehouse_id: str
    hour: datetime
    cost: Decimal


def idle_hours(hours: list[WarehouseHour], busy: frozenset[tuple[str, datetime]]) -> list[WarehouseHour]:
    """Hora faturada sem nenhuma consulta começando ou rodando nela."""
    return [item for item in hours if (item.warehouse_id, item.hour) not in busy]


def detect_idle_warehouse(
    hours: list[WarehouseHour],
    busy: frozenset[tuple[str, datetime]] | None,
    now: datetime,
    policy: Policy,
) -> DetectorOutcome:
    if busy is None:
        return not_evaluated(OCIOSO, "system.query.history indisponível para a identidade do ciclo")
    inicio = now - timedelta(days=policy.estimate_window_days)
    janela = [item for item in hours if item.hour >= inicio]
    ociosas = idle_hours(janela, busy)
    por_warehouse: dict[str, list[WarehouseHour]] = {}
    for item in ociosas:
        por_warehouse.setdefault(item.warehouse_id, []).append(item)
    faturadas = {item.warehouse_id: 0 for item in janela}
    for item in janela:
        faturadas[item.warehouse_id] += 1
    candidatas = []
    for warehouse_id, lista in sorted(por_warehouse.items()):
        total = sum((item.cost for item in lista), ZERO)
        candidatas.append(
            Opportunity(
                opportunity_id(OCIOSO, warehouse_id, month_label(now)), OCIOSO, warehouse_id, warehouse_id, "",
                month_label(now), measured(total, len(lista), policy.estimate_window_days, policy),
                None, CONFIDENCE_LABELS[OCIOSO],
                evidence=(f"{len(lista)} de {faturadas[warehouse_id]} horas faturadas sem consulta",),
                unit="custo de horas ociosas",
            )
        )
    return _outcome(OCIOSO, len(faturadas), candidatas, policy)


def assign_groups(opportunities: list[Opportunity], now: datetime) -> list[Opportunity]:
    """Grupo de exclusão por (job, mês): a schedule contém as demais; o warehouse é seu próprio grupo."""
    grupos: dict[str, list[Opportunity]] = {}
    for item in opportunities:
        chave = item.job_id or f"warehouse:{item.subject}"
        grupos.setdefault(stable_id("sgp", chave, month_label(now)), []).append(item)
    resultado = []
    for group_id, itens in sorted(grupos.items()):
        schedule = next((item for item in itens if item.source == SCHEDULE), None)
        for item in itens:
            contida = schedule is not None and item is not schedule
            resultado.append(
                replace(
                    item, group_id=group_id,
                    contained_in=schedule.opportunity_id if contida else "",
                    counted=not contida,
                )
            )
    return resultado


def risk(
    job_name: str,
    producer_assets: dict[str, tuple[str, ...]],
    edges: tuple[Edge, ...],
    now: datetime,
) -> tuple[str, str]:
    """Alto: consumo humano só por arestas confirmadas. Médio: por aresta incerta, ou sem ativo mapeado."""
    ativos = producer_assets.get(normalize(job_name), ())
    if not ativos:
        return MEDIO, "dependências desconhecidas: nenhum ativo com contrato produzido por este job"
    confirmadas = tuple(edge for edge in edges if not edge.is_uncertain)
    for conjunto, nivel, prefixo in ((confirmadas, ALTO, "alimenta"), (edges, MEDIO, "pode alimentar")):
        for ativo in ativos:
            humanos = [node for node in traverse(conjunto, ativo, now).nodes if node.is_human_consumption]
            if humanos:
                painel = sorted(node.asset for node in humanos)[0]
                sufixo = " — verificar SLO antes" if nivel == ALTO else " (aresta incerta)"
                return nivel, f"{prefixo} {painel}{sufixo}"
    return BAIXO, "sem consumidor humano na lineage"


def link_initiatives(
    opportunities: list[Opportunity],
    initiatives: list[dict],
    realization_states: dict[str, str],
) -> list[Opportunity]:
    """Iniciativa ativa na mesma (fonte, sujeito) ⇒ `em_iniciativa`, fora do KPI; descartada some."""
    descartadas = {item["opportunity_id"] for item in initiatives if item.get("state") == DESCARTADA}
    ativas: dict[tuple[str, str], str] = {}
    for item in initiatives:
        if item.get("state") == APROVADA or (
            item.get("state") == IMPLEMENTADA and realization_states.get(item["initiative_id"]) not in TERMINAL
        ):
            ativas[(item["source"], item["subject"])] = item["initiative_id"]
    resultado = []
    for oportunidade in opportunities:
        if oportunidade.opportunity_id in descartadas:
            continue
        iniciativa = ativas.get((oportunidade.source, oportunidade.subject))
        if iniciativa:
            oportunidade = replace(oportunidade, status=EM_INICIATIVA, initiative_id=iniciativa, counted=False)
        resultado.append(oportunidade)
    return resultado


@dataclass(frozen=True)
class Realization:
    initiative_id: str
    state: str
    unit: str
    baseline_median: Decimal | None = None
    after_median: Decimal | None = None
    n_before: int = 0
    n_after: int = 0
    monthly_volume: float | None = None
    gross_usd: Decimal | None = None
    net_usd: Decimal | None = None
    side_effect_incidents: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""


POR_MILHAO = "custo por milhão de linhas"
POR_RUN = "custo por run"
POR_RUN_BEM_SUCEDIDO = "custo total por run bem-sucedido"
POR_DIA = "custo por dia"


def _per_run_values(runs: list[RunRecord], per_million: bool) -> list[Decimal]:
    if per_million:
        return [run.cost / Decimal(run.input_rows) * MILLION for run in runs]
    return [run.cost for run in runs]


def _run_unit(
    source: str, before: list[RunRecord], after: list[RunRecord], recent: list[RunRecord]
) -> tuple[str, Decimal | None, Decimal | None, int, int, Decimal]:
    """(unidade, mediana antes, mediana depois, n antes, n depois, volume mensal)."""
    if source == FALHA:
        def razao(runs: list[RunRecord]) -> tuple[Decimal | None, int]:
            sucesso = [run for run in runs if run.succeeded]
            custo = sum((run.cost for run in runs if run.cost is not None), ZERO)
            return (custo / len(sucesso) if sucesso else None), len(sucesso)

        antes, n_antes = razao(before)
        depois, n_depois = razao(after)
        return POR_RUN_BEM_SUCEDIDO, antes, depois, n_antes, n_depois, Decimal(
            sum(1 for run in recent if run.succeeded)
        )

    def validos(runs: list[RunRecord], exige_linhas: bool) -> list[RunRecord]:
        return [
            run for run in runs
            if run.succeeded and run.cost is not None and (not exige_linhas or (run.input_rows or 0) > 0)
        ]

    por_milhao = bool(validos(before, True)) and bool(validos(after, True))
    antes, depois = validos(before, por_milhao), validos(after, por_milhao)
    mediana_antes = statistics.median(_per_run_values(antes, por_milhao)) if antes else None
    mediana_depois = statistics.median(_per_run_values(depois, por_milhao)) if depois else None
    recentes = validos(recent, por_milhao)
    volume = (
        Decimal(sum(run.input_rows for run in recentes)) / MILLION if por_milhao else Decimal(len(recentes))
    )
    return (
        POR_MILHAO if por_milhao else POR_RUN, mediana_antes, mediana_depois, len(antes), len(depois), volume
    )


def measure(
    initiative: dict,
    runs: list[RunRecord],
    daily_costs: dict[date, Decimal],
    side_effects: list[dict],
    now: datetime,
    policy: Policy,
) -> Realization | None:
    """Mede uma iniciativa implementada. `runs` e `daily_costs` são do sujeito da iniciativa."""
    if initiative.get("state") != IMPLEMENTADA or initiative.get("implemented_at") is None:
        return None
    ancora: datetime = initiative["implemented_at"]
    medida = timedelta(days=policy.measure_days)
    iniciativa_id = initiative["initiative_id"]
    if now < ancora + medida:
        return Realization(iniciativa_id, EM_MEDICAO, "", reason=f"janela depois fecha em {ancora + medida:%d/%m}")
    fim_depois = ancora + medida
    fonte = initiative["source"]
    if fonte in (SCHEDULE, OCIOSO):
        dias = range(policy.measure_days)
        dias_antes = [daily_costs.get((ancora - timedelta(days=i + 1)).date(), ZERO) for i in dias]
        dias_depois = [daily_costs.get((ancora + timedelta(days=i)).date(), ZERO) for i in dias]
        unidade, antes, depois = POR_DIA, statistics.median(dias_antes), statistics.median(dias_depois)
        n_antes = n_depois = policy.measure_days
        volume = Decimal(policy.estimate_window_days)
        fim_usado = fim_depois
        suficiente = True
    else:
        janela_antes = [run for run in runs if ancora - medida <= run.start_time < ancora]
        recentes = [run for run in runs if run.start_time >= now - timedelta(days=policy.estimate_window_days)]

        def depois_ate(limite: datetime) -> list[RunRecord]:
            return [run for run in runs if ancora <= run.start_time < limite]

        fim_usado = fim_depois
        unidade, antes, depois, n_antes, n_depois, volume = _run_unit(
            fonte, janela_antes, depois_ate(fim_usado), recentes
        )
        if n_depois < policy.min_runs:
            fim_usado = min(now, ancora + timedelta(days=policy.expiry_days))
            unidade, antes, depois, n_antes, n_depois, volume = _run_unit(
                fonte, janela_antes, depois_ate(fim_usado), recentes
            )
        suficiente = n_antes >= policy.min_runs and n_depois >= policy.min_runs
    if not suficiente or antes is None or depois is None:
        expirou = now >= ancora + timedelta(days=policy.expiry_days)
        return Realization(
            iniciativa_id, EXPIRADA if expirou else AMOSTRA_INSUFICIENTE, unidade, antes, depois, n_antes, n_depois,
            reason=f"{n_antes} runs antes e {n_depois} depois; mínimo {policy.min_runs} de cada lado",
        )
    bruta = (antes - depois) * volume
    custo = initiative.get("implementation_cost_usd")
    liquida = bruta - Decimal(str(custo)) if custo is not None else None
    decisiva = liquida if liquida is not None else bruta
    colaterais = tuple(
        sorted(
            item["incident_id"] for item in side_effects
            if item.get("type") in SIDE_EFFECT_TYPES
            and item.get("detected_at") is not None
            and ancora <= item["detected_at"] < fim_usado
        )
    )
    if decisiva <= 0:
        estado, motivo = NAO_REALIZADA, "custo por unidade não caiu o bastante para cobrir a mudança"
    elif colaterais:
        estado, motivo = EFEITO_COLATERAL, "economia com incidente de qualidade ou SLA na janela depois"
    else:
        estado, motivo = REALIZADA, ""
    if liquida is None:
        motivo = (motivo + "; " if motivo else "") + "líquida não calculada (sem custo de implementação)"
    return Realization(
        iniciativa_id, estado, unidade, antes, depois, n_antes, n_depois, float(volume), bruta, liquida,
        colaterais, motivo,
    )
