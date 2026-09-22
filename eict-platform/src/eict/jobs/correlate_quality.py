"""Transforma resultados de regra em incidentes de qualidade.

Fica separado do correlator de runtime porque os sinais são outros: o assunto é o
ativo, as hipóteses são de pipeline e origem, e a evidência carrega a consulta.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from eict.adapters import store
from eict.config import Settings
from eict.domain import quality_hypotheses
from eict.domain.contracts import Contract
from eict.domain.incidents import (
    CONTRACT_VIOLATION,
    QUALITY_ENGINE_FAILURE,
    open_or_update_for_asset,
)
from eict.domain.models import Change, Incident, RuleResult, TimelineEntry
from eict.domain.quality_incidents import (
    build_error_evidence,
    build_evidence,
    first_result_id,
    group_errors,
    group_violations,
    has_blocking,
    incident_severity,
    violation_summary,
)

logger = logging.getLogger(__name__)

RESULT_WINDOW = timedelta(hours=6)


@dataclass(frozen=True)
class QualityInput:
    results: list[RuleResult]
    contracts: dict[str, Contract]
    changes: list[Change]
    producer_states: dict[str, bool]


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


def correlate_quality(
    payload: QualityInput,
    open_incidents: list[Incident],
    tenant_id: str,
    now: datetime,
) -> tuple[list[Incident], list[TimelineEntry], list, list]:
    """Devolve incidentes tocados, entradas de timeline, evidências e hipóteses."""
    incidents: list[Incident] = list(open_incidents)
    touched: list[Incident] = []
    entries: list[TimelineEntry] = []
    evidences: list = []
    hypotheses: list = []

    for asset, results in group_violations(payload.results).items():
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

        asset_evidences = [build_evidence(result, now) for result in results]
        analysis = quality_hypotheses.analyze(
            _context_for(asset, results, contract, payload), incident.incident_id, now
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

        evidences.extend(asset_evidences + list(analysis.evidence))
        hypotheses.extend(analysis.hypotheses)
        incidents = [item for item in incidents if item.subject != incident.subject]
        incidents.append(incident)
        touched.append(incident)

    for asset, errors in group_errors(payload.results).items():
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
        evidences.extend(error_evidences)
        touched.append(incident)

    return touched, entries, evidences, hypotheses


def persist(
    spark: Any,
    settings: Settings,
    incidents: list[Incident],
    entries: list[TimelineEntry],
    evidences: list,
    hypotheses: list,
) -> None:
    if incidents:
        store.merge_rows(
            spark,
            settings.table("ops", "incidents"),
            [store.incident_row(incident) for incident in incidents],
            ["correlation_key"],
        )
    by_incident = {incident.incident_id for incident in incidents}
    incident_id = next(iter(by_incident), "")
    if evidences:
        store.insert_missing(
            spark,
            settings.table("ops", "evidence"),
            [store.evidence_row(incident_id, evidence) for evidence in evidences],
            "evidence_id",
        )
    if hypotheses:
        store.merge_rows(
            spark,
            settings.table("ops", "hypotheses"),
            [store.hypothesis_row(incident_id, hypothesis) for hypothesis in hypotheses],
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
    asset: str, results: list[RuleResult], contract: Contract | None, payload: QualityInput
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
        changes=tuple(payload.changes),
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
