"""Resumo executivo (SPEC-017, DASH-01): saúde, riscos, SLA e impacto, cada número com a sua prova.

A regra da SPEC que orienta tudo aqui: **toda métrica informa janela, fonte, amostra, fórmula e
confiança**. Um MTTR de 3 horas sobre 2 incidentes não é o mesmo número que sobre 200 — e o
gestor precisa ver a diferença. Onde não há dado, o valor é "não medido", nunca zero: MTTA sem
reconhecimento é pendente, não instantâneo.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

WINDOW = timedelta(days=7)
POLICY_VERSION = "exec-summary-v1"

ALTA = "alta"
BAIXA = "baixa"
SEM_DADOS = "sem_dados"
MIN_CONFIDENT_SAMPLE = 5

ACTIVE_STATES = frozenset({"detected", "triaged", "investigating", "mitigating", "monitoring"})
_SEVERIDADES = ("blocking", "critical", "high", "warning", "info")


@dataclass(frozen=True)
class Metric:
    metric_id: str
    label: str
    value: float | None
    unit: str
    window: str
    source: str
    n: int
    formula: str
    confidence: str
    detail: str = ""


def _confidence(n: int) -> str:
    if n == 0:
        return SEM_DADOS
    return ALTA if n >= MIN_CONFIDENT_SAMPLE else BAIXA


def _hours(delta: timedelta) -> float:
    return delta.total_seconds() / 3600


def summarize(
    incidents: list[dict],
    costs: dict[str, dict],
    connector_health: list[dict],
    now: datetime,
) -> list[Metric]:
    """`incidents` e `connector_health` são linhas das tabelas; `costs` é `run_cost` por run."""
    ativos = [item for item in incidents if item["state"] in ACTIVE_STATES]
    janela = now - WINDOW
    return [
        _active(ativos),
        _severity(ativos),
        _mttr(incidents, janela),
        _administrative(incidents, janela),
        _mtta(incidents, ativos, janela),
        _sla_risk(ativos),
        _impact(ativos),
        _cost(ativos, costs),
        _connectors(connector_health),
    ]


def _active(ativos: list[dict]) -> Metric:
    tipos: dict[str, int] = {}
    for item in ativos:
        tipos[item["type"]] = tipos.get(item["type"], 0) + 1
    detalhe = ", ".join(f"{tipo}: {n}" for tipo, n in sorted(tipos.items(), key=lambda par: -par[1]))
    return Metric(
        "active_incidents", "Incidentes ativos", float(len(ativos)), "incidentes", "agora",
        "ops.incidents", len(ativos), "count distinct incident_id com estado ativo",
        ALTA, detalhe or "nenhum",
    )


def _severity(ativos: list[dict]) -> Metric:
    graves = [item for item in ativos if item["severity"] in ("blocking", "critical")]
    por_sev = {sev: sum(1 for item in ativos if item["severity"] == sev) for sev in _SEVERIDADES}
    detalhe = " · ".join(f"{sev} {n}" for sev, n in por_sev.items() if n)
    return Metric(
        "critical_incidents", "Críticos ou bloqueantes", float(len(graves)), "incidentes", "agora",
        "ops.incidents", len(ativos), "ativos com severity em (critical, blocking)",
        ALTA, detalhe or "nenhum",
    )


def _mttr(incidents: list[dict], janela: datetime) -> Metric:
    """Só recuperação (`recovered`): fechamento por decisão não é o serviço voltando."""
    duracoes = [
        _hours(item["updated_at"] - item["detected_at"])
        for item in incidents
        if item["state"] == "recovered" and item["updated_at"] >= janela
    ]
    mediana = statistics.median(duracoes) if duracoes else None
    return Metric(
        "mttr_hours", "MTTR operacional (mediana)", mediana, "horas", "7 dias",
        "ops.incidents (state=recovered)", len(duracoes), "mediana de recovered_at − detected_at",
        _confidence(len(duracoes)),
        f"p90 {statistics.quantiles(duracoes, n=10)[-1]:.1f} h" if len(duracoes) >= 2 else "",
    )


def _administrative(incidents: list[dict], janela: datetime) -> Metric:
    fechados = [item for item in incidents if item["state"] == "closed" and item["updated_at"] >= janela]
    return Metric(
        "administrative_closures", "Fechamentos por decisão", float(len(fechados)), "incidentes", "7 dias",
        "ops.incidents (state=closed)", len(fechados),
        "count de closed na janela — medido à parte do MTTR (SPEC-017)", ALTA,
        "aceite de regime, superação de risco de SLA",
    )


def _mtta(incidents: list[dict], ativos: list[dict], janela: datetime) -> Metric:
    """Sem reconhecimento, o incidente fica pendente — nunca entra como zero (SPEC-017)."""
    duracoes = [
        _hours(item["acknowledged_at"] - item["detected_at"])
        for item in incidents
        if item.get("acknowledged_at") and item["detected_at"] >= janela
    ]
    pendentes = sum(1 for item in ativos if not item.get("acknowledged_at"))
    mediana = statistics.median(duracoes) if duracoes else None
    return Metric(
        "mtta_hours", "MTTA (mediana)", mediana, "horas", "7 dias",
        "ops.incidents (acknowledged_at)", len(duracoes), "mediana de acknowledged_at − detected_at",
        _confidence(len(duracoes)),
        f"{pendentes} ativo(s) sem reconhecimento" if pendentes else ("" if duracoes else "nenhum reconhecimento"),
    )


def _sla_risk(ativos: list[dict]) -> Metric:
    riscos = [item for item in ativos if item["type"] == "sla_risk"]
    return Metric(
        "sla_at_risk", "SLAs em risco", float(len(riscos)), "ativos", "agora",
        "ops.incidents (type=sla_risk)", len(riscos), "sla_risk ativos",
        ALTA, ", ".join(sorted(item["subject"] for item in riscos)) or "nenhum",
    )


def _impact(ativos: list[dict]) -> Metric:
    com_raio = sorted(
        (item for item in ativos if (item.get("impact_score") or 0) > 0),
        key=lambda item: -(item.get("impact_score") or 0),
    )
    topo = "; ".join(
        f"{item['subject'].split('.')[-1]} ({item['impact_score']:.2f}, "
        f"{len(item.get('affected_assets') or [])} ativos)"
        for item in com_raio[:3]
    )
    alcancados = {asset for item in ativos for asset in (item.get("affected_assets") or [])}
    return Metric(
        "impacted_assets", "Ativos atingidos", float(len(alcancados)), "ativos", "agora",
        "ops.incidents.affected_assets (lineage)", len(com_raio),
        "união dos ativos no raio dos incidentes ativos", ALTA if com_raio else SEM_DADOS,
        topo or "nenhum incidente com raio calculado",
    )


def _cost(ativos: list[dict], costs: dict[str, dict]) -> Metric:
    """Soma só o que o billing confirmou; pendentes aparecem, não viram zero."""
    disponiveis, pendentes = [], 0
    for item in ativos:
        custo = costs.get(item.get("last_run_id") or "")
        if not custo:
            continue
        if custo.get("status") == "available" and custo.get("incremental_cost_usd") is not None:
            disponiveis.append(float(custo["incremental_cost_usd"]))
        elif custo.get("status") == "pending":
            pendentes += 1
    total = sum(disponiveis) if disponiveis else None
    return Metric(
        "incremental_cost_usd", "Custo incremental dos incidentes ativos", total, "US$", "agora",
        "ops.run_cost (system.billing)", len(disponiveis),
        "Σ incremental_cost_usd do último run de cada incidente ativo",
        _confidence(len(disponiveis)), f"{pendentes} pendente(s) no billing" if pendentes else "",
    )


def _connectors(health: list[dict]) -> Metric:
    ruins = [item for item in health if item.get("status") in ("falhando", "degradado")]
    detalhe = "; ".join(f"{item['connector']}: {item['status']}" for item in health)
    return Metric(
        "unhealthy_connectors", "Conectores com problema", float(len(ruins)) if health else None,
        "conectores", "último ciclo", "ops.connector_health", len(health),
        "conectores em degradado ou falhando", ALTA if health else SEM_DADOS, detalhe or "sem avaliação",
    )


def rows(metrics: list[Metric], computed_at: datetime) -> list[dict]:
    return [
        {
            "metric_id": item.metric_id,
            "label": item.label,
            "value": item.value,
            "unit": item.unit,
            "window": item.window,
            "source": item.source,
            "n": item.n,
            "formula": item.formula,
            "confidence": item.confidence,
            "detail": item.detail,
            "policy_version": POLICY_VERSION,
            "computed_at": computed_at,
        }
        for item in metrics
    ]
