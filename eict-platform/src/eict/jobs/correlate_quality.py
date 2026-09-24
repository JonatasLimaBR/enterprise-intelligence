"""Transforma resultados de regra em incidentes de qualidade.

Fica separado do correlator de runtime porque os sinais são outros: o assunto é o
ativo, as hipóteses são de pipeline e origem, e a evidência carrega a consulta.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from eict.adapters import store
from eict.config import Settings
from eict.domain import impact as impact_rules
from eict.domain import quality_hypotheses
from eict.domain import semantic_incidents as semantic
from eict.domain import sla as sla_rules
from eict.domain.contracts import Contract
from eict.domain.extraction import ObservedMetric
from eict.domain.incidents import (
    CONTRACT_VIOLATION,
    QUALITY_ENGINE_FAILURE,
    SEMANTIC_CONFLICT,
    SLA_RISK,
    open_or_update_for_asset,
)
from eict.domain.metrics import Divergence
from eict.domain.models import Change, Evidence, Incident, RuleResult, TimelineEntry
from eict.domain.quality_incidents import (
    build_error_evidence,
    build_evidence,
    first_result_id,
    group_errors,
    group_violations,
    has_blocking,
    incident_severity,
    latest_per_rule,
    violation_summary,
)
from eict.domain.resolution import resolvable
from eict.domain.severity import rank_of

logger = logging.getLogger(__name__)

RESULT_WINDOW = timedelta(hours=6)


@dataclass(frozen=True)
class QualityInput:
    results: list[RuleResult]
    contracts: dict[str, Contract]
    changes: list[Change]
    producer_states: dict[str, bool]
    graph: tuple[impact_rules.Edge, ...] = ()
    changed_upstream: frozenset[str] = frozenset()
    max_depth: int = impact_rules.DEFAULT_MAX_DEPTH
    excluded: tuple[str, ...] = ()
    semantics: SemanticInput | None = None
    sla: tuple[sla_rules.Assessment, ...] | None = None


@dataclass(frozen=True)
class SemanticInput:
    """O que a etapa `semantics` observou neste ciclo e o que o registry manda ler.

    `None` no payload significa "não houve extração": nenhum incidente semântico abre e
    nenhum fecha. Lista vazia com `sources` preenchido significa "extraiu e não achou nada".
    """

    observed: list[ObservedMetric]
    sources: tuple[tuple[str, str], ...]
    divergences: tuple[Divergence, ...]


def load_recent_results(spark: Any, settings: Settings, now: datetime) -> list[RuleResult]:
    limite = (now - RESULT_WINDOW).isoformat(sep=" ", timespec="seconds")
    records = store.query(
        spark,
        f"""
        SELECT * FROM {settings.table('ops', 'rule_results')}
        WHERE evaluated_at >= TIMESTAMP '{limite}'
        """,
    )
    return [_to_result(record) for record in records]


def load_semantic_state(spark: Any, settings: Settings, now: datetime) -> SemanticInput | None:
    """Reconstrói a última extração gravada e repete a comparação com o registry atual.

    Só o lote mais recente conta: uma linha de extração antiga (métrica que mudou de linha
    ou saiu do código) continua na tabela, e somá-la inventaria conflito. Sem lote na
    janela, devolve `None` — a etapa não rodou, e nada semântico abre nem fecha.
    """
    from eict.adapters import metric_loader
    from eict.domain.metrics import compare
    from eict.jobs.semantics import metrics_dir

    limite = (now - RESULT_WINDOW).isoformat(sep=" ", timespec="seconds")
    tabela = settings.table("ops", "metrics")
    records = store.query(
        spark,
        f"""
        SELECT * FROM {tabela}
        WHERE observed_at = (SELECT max(observed_at) FROM {tabela})
          AND observed_at >= TIMESTAMP '{limite}'
        """,
    )
    if not records:
        return None
    registry = metric_loader.load_registry(metrics_dir(settings))
    observed = [_to_observed(record) for record in records]
    return SemanticInput(
        observed=observed,
        sources=registry.sources,
        divergences=compare(list(registry.declarations), observed),
    )


def correlate_quality(
    payload: QualityInput,
    open_incidents: list[Incident],
    tenant_id: str,
    now: datetime,
) -> tuple[list[Incident], list[TimelineEntry], list, list]:
    """Devolve incidentes tocados, timeline, e os pares (incident_id, item).

    Evidência e hipótese viajam emparelhadas com o incidente que as gerou: um ciclo
    toca vários ativos, e sem o par elas acabariam todas arquivadas debaixo de um só.
    """
    incidents: list[Incident] = list(open_incidents)
    touched: list[Incident] = []
    entries: list[TimelineEntry] = []
    evidences: list[tuple[str, Any]] = []
    hypotheses: list[tuple[str, Any]] = []

    current = latest_per_rule(payload.results)

    for asset, results in group_violations(current).items():
        incident, created = open_or_update_for_asset(
            incidents,
            tenant_id,
            asset,
            CONTRACT_VIOLATION,
            first_result_id(results),
            now,
            severity=incident_severity(results),
        )
        contract = payload.contracts.get(asset)
        if contract is not None:
            incident = incident.with_declared_consumers(tuple(contract.consumers))

        radius = _impact_of(asset, payload, now)
        if radius.nodes:
            subida = impact_rules.escalation(incident.severity, radius)
            incident = incident.with_impact(
                assets=radius.assets,
                score=radius.score,
                policy_version=radius.policy_version,
                severity=subida.to_severity if subida else None,
                escalation_reason=subida.reason if subida else "",
            )

        asset_evidences = [build_evidence(result, now) for result in results]
        analysis = quality_hypotheses.analyze(
            _context_for(asset, results, contract, payload, now), incident.incident_id, now
        )

        entries.append(
            TimelineEntry.create(
                incident_id=incident.incident_id,
                at=now,
                kind="detected" if created else "recurrence",
                summary=violation_summary(asset, results),
                evidence_ids=tuple(item.evidence_id for item in asset_evidences),
            )
        )
        if has_blocking(results):
            entries.append(
                TimelineEntry.create(
                    incident_id=incident.incident_id,
                    at=now,
                    kind="blocking_gate",
                    summary="violação bloqueante de schema: consumidores devem ser avisados",
                )
            )

        evidences.extend(
            (incident.incident_id, item) for item in asset_evidences + list(analysis.evidence)
        )
        hypotheses.extend((incident.incident_id, item) for item in analysis.hypotheses)
        incidents = _replacing(incidents, incident)
        touched.append(incident)

    for asset, errors in group_errors(current).items():
        incident, created = open_or_update_for_asset(
            incidents, tenant_id, asset, QUALITY_ENGINE_FAILURE, first_result_id(errors), now
        )
        error_evidences = [build_error_evidence(result, now) for result in errors]
        entries.append(
            TimelineEntry.create(
                incident_id=incident.incident_id,
                at=now,
                kind="detected" if created else "recurrence",
                summary=f"{len(errors)} regra(s) não puderam ser avaliadas em {asset}",
                evidence_ids=tuple(item.evidence_id for item in error_evidences),
            )
        )
        evidences.extend((incident.incident_id, item) for item in error_evidences)
        incidents = _replacing(incidents, incident)
        touched.append(incident)

    if payload.semantics is not None:
        for asset, divergences in semantic.group_conflicts(payload.semantics.divergences).items():
            incident, created = open_or_update_for_asset(
                incidents,
                tenant_id,
                asset,
                SEMANTIC_CONFLICT,
                semantic.event_id(divergences),
                now,
                severity=semantic.DEFAULT_SEVERITY,
            )
            radius = _impact_of(asset, payload, now)
            if radius.nodes:
                subida = impact_rules.escalation(incident.severity, radius)
                incident = incident.with_impact(
                    assets=radius.assets,
                    score=radius.score,
                    policy_version=radius.policy_version,
                    severity=subida.to_severity if subida else None,
                    escalation_reason=subida.reason if subida else "",
                )
            divergence_evidences = [
                semantic.build_evidence(item, payload.semantics.observed, now) for item in divergences
            ]
            entries.append(
                TimelineEntry.create(
                    incident_id=incident.incident_id,
                    at=now,
                    kind="detected" if created else "recurrence",
                    summary=semantic.conflict_summary(asset, divergences),
                    evidence_ids=tuple(item.evidence_id for item in divergence_evidences),
                )
            )
            evidences.extend((incident.incident_id, item) for item in divergence_evidences)
            incidents = _replacing(incidents, incident)
            touched.append(incident)

    if payload.sla is not None:
        for item in payload.sla:
            if not item.at_risk:
                continue
            incident, created = _open_sla_risk(incidents, tenant_id, item, now)
            radius = _impact_of(item.asset, payload, now)
            if radius.nodes:
                subida = impact_rules.escalation(incident.severity, radius)
                incident = incident.with_impact(
                    assets=radius.assets,
                    score=radius.score,
                    policy_version=radius.policy_version,
                    severity=subida.to_severity if subida else None,
                    escalation_reason=subida.reason if subida else "",
                )
            evidencia = _sla_evidence(item, now)
            entries.append(
                TimelineEntry.create(
                    incident_id=incident.incident_id,
                    at=now,
                    kind="detected" if created else "recurrence",
                    summary=sla_rules.summary(item),
                    evidence_ids=(evidencia.evidence_id,),
                )
            )
            evidences.append((incident.incident_id, evidencia))
            incidents = _replacing(incidents, incident)
            touched.append(incident)

        # A superação vem antes da resolução: `violado` não é "avaliado e sem risco". Se entrasse
        # na resolução, o risco que virou violação seria fechado como `recovered` — uma mentira.
        violados = frozenset(item.asset for item in payload.sla if item.klass == sla_rules.VIOLADO)
        for incident, entry in sla_rules.superseded(incidents, violados, SLA_RISK, now):
            entries.append(entry)
            incidents = _replacing(incidents, incident)
            touched.append(incident)

    avaliados, violando = _current_state(current)
    if payload.sla is not None:
        avaliados = avaliados | frozenset(
            (item.asset, SLA_RISK)
            for item in payload.sla
            if item.klass in (sla_rules.NO_PRAZO, *sla_rules.AT_RISK)
        )
        violando = violando | frozenset((item.asset, SLA_RISK) for item in payload.sla if item.at_risk)
    if payload.semantics is not None:
        sem_avaliados, sem_violando = semantic.current_state(
            payload.semantics.observed, payload.semantics.sources, payload.semantics.divergences
        )
        avaliados, violando = avaliados | sem_avaliados, violando | sem_violando
    resolvidos = resolvable(incidents, avaliados, violando, now)
    for incident, entry in resolvidos:
        entries.append(entry)
        touched.append(incident)

    return touched, entries, evidences, hypotheses


def _open_sla_risk(incidents: list[Incident], tenant_id: str, item, now: datetime) -> tuple[Incident, bool]:
    """Abre ou atualiza o risco do ativo; a severidade acompanha a piora (em risco → inevitável)."""
    event_id = f"sla-{item.asset}-{item.deadline:%Y%m%dT%H%M}"
    incident, created = open_or_update_for_asset(
        incidents, tenant_id, item.asset, SLA_RISK, event_id, now, severity=item.severity
    )
    if not created and rank_of(item.severity) > rank_of(incident.severity):
        incident = replace(incident, severity=item.severity)
    return incident, created


def _sla_evidence(item, now: datetime) -> Evidence:
    payload = {
        "slo_kind": item.slo_kind,
        "deadline": item.deadline.isoformat() if item.deadline else None,
        "klass": item.klass,
        "slack_s": item.slack_s,
        "remaining_s": item.remaining_s,
        "cycle_latency_s": sla_rules.LATENCIA_CICLO_S,
        "margin_s": sla_rules.MARGEM_S,
        "producer_job_id": item.producer_job_id,
        "producer_state": item.producer_state,
        "policy_version": sla_rules.POLICY_VERSION,
    }
    return Evidence.create(
        kind="sla_prediction",
        source_ref=f"sla/{item.asset}/{item.slo_kind}/{item.deadline:%Y%m%dT%H%M}",
        observed_at=now,
        summary=sla_rules.summary(item),
        value=json.dumps(payload, ensure_ascii=False),
    )


def _current_state(results: list[RuleResult]) -> tuple[frozenset, frozenset]:
    """O que foi avaliado agora, e o que ainda viola.

    Avaliado é o ativo com **qualquer** resultado corrente — inclusive `passed`. Sem essa
    distinção, um ativo cuja etapa de qualidade não rodou pareceria consertado.
    """
    avaliados: set = set()
    violando: set = set()
    for result in results:
        for tipo in (CONTRACT_VIOLATION, QUALITY_ENGINE_FAILURE):
            avaliados.add((result.asset, tipo))
        if result.is_violation:
            violando.add((result.asset, CONTRACT_VIOLATION))
        if result.is_error:
            violando.add((result.asset, QUALITY_ENGINE_FAILURE))
    return frozenset(avaliados), frozenset(violando)


def _replacing(incidents: list[Incident], incident: Incident) -> list[Incident]:
    """Troca o incidente na lista pela versão recém-tocada.

    A identidade é assunto **e** tipo: o mesmo ativo pode ter ao mesmo tempo uma
    violação de contrato e uma falha do motor de avaliação, e descartar por assunto
    faria a segunda renascer com id novo a cada ciclo.
    """
    outros = [
        item
        for item in incidents
        if (item.subject, item.type) != (incident.subject, incident.type)
    ]
    return [*outros, incident]


def persist(
    spark: Any,
    settings: Settings,
    incidents: list[Incident],
    entries: list[TimelineEntry],
    evidences: list[tuple[str, Any]],
    hypotheses: list[tuple[str, Any]],
) -> None:
    if incidents:
        store.merge_rows(
            spark,
            settings.table("ops", "incidents"),
            [store.incident_row(incident) for incident in incidents],
            ["correlation_key"],
        )
    if evidences:
        store.insert_missing(
            spark,
            settings.table("ops", "evidence"),
            [store.evidence_row(incident_id, item) for incident_id, item in evidences],
            "evidence_id",
        )
    if hypotheses:
        store.merge_rows(
            spark,
            settings.table("ops", "hypotheses"),
            [store.hypothesis_row(incident_id, item) for incident_id, item in hypotheses],
            ["hypothesis_id"],
        )
    if entries:
        store.insert_missing(
            spark,
            settings.table("ops", "incident_timeline"),
            [store.timeline_row(entry) for entry in entries],
            "entry_id",
        )


def _context_for(
    asset: str,
    results: list[RuleResult],
    contract: Contract | None,
    payload: QualityInput,
    now: datetime,
) -> quality_hypotheses.QualityContext:
    principal = results[0]
    producer = contract.producer if contract else ""
    return quality_hypotheses.QualityContext(
        asset=asset,
        dimension=principal.dimension,
        rule_expression=principal.rule_id,
        producer_job_id=producer,
        producer_failed=payload.producer_states.get(producer) is False,
        producer_ran_in_window=payload.producer_states.get(producer, True),
        upstream_schema_changed=bool(_changed_upstream_of(asset, payload, now)),
        changes=tuple(payload.changes),
    )


def _changed_upstream_of(
    asset: str, payload: QualityInput, now: datetime
) -> tuple[str, ...]:
    """Ativos a montante cuja impressão digital de schema mudou.

    Sem isto, `upstream_change` ficava travada em 0,05 em toda execução: a hipótese
    existia e nunca tinha como pontuar.
    """
    if not payload.graph or not payload.changed_upstream:
        return ()
    origem = impact_rules.traverse(
        payload.graph,
        asset,
        now,
        direction=impact_rules.UPSTREAM,
        max_depth=payload.max_depth,
        excluded=payload.excluded,
    )
    return impact_rules.changed_sources(origem, payload.changed_upstream)


def _impact_of(asset: str, payload: QualityInput, now: datetime) -> impact_rules.ImpactResult:
    return impact_rules.traverse(
        payload.graph,
        asset,
        now,
        direction=impact_rules.DOWNSTREAM,
        max_depth=payload.max_depth,
        excluded=payload.excluded,
    )


def _to_result(record: dict) -> RuleResult:
    return RuleResult(
        result_id=record["result_id"],
        contract_id=record["contract_id"],
        rule_id=record["rule_id"],
        asset=record["asset"],
        dimension=record["dimension"],
        status=record["status"],
        threshold=record.get("threshold") or "",
        severity=record.get("severity") or "warning",
        window=record.get("window") or "",
        query_hash=record.get("query_hash") or "",
        evaluated_at=record["evaluated_at"],
        numerator=int(record.get("numerator") or 0),
        denominator=int(record.get("denominator") or 0),
        error_message=record.get("error_message"),
    )


def _to_observed(record: dict) -> ObservedMetric:
    return ObservedMetric(
        metric_id=record.get("metric_id") or "",
        asset=record.get("asset") or "",
        formula_raw=record.get("formula_raw") or "",
        formula_hash=record.get("formula_hash") or "",
        grain=tuple(record.get("grain") or ()),
        source_path=record.get("source_path") or "",
        source_line=int(record.get("source_line") or 0),
        status=record.get("extraction_status") or "",
        detail=record.get("extraction_detail") or "",
    )
