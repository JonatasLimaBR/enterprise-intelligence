from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from eict.domain.baseline import Baseline
from eict.domain.models import Hypothesis, Incident, Run, TimelineEntry, stable_id

RUNTIME_REGRESSION = "runtime_regression"
CONTRACT_VIOLATION = "contract_violation"
QUALITY_ENGINE_FAILURE = "quality_engine_failure"
SEMANTIC_CONFLICT = "semantic_conflict"
DEFAULT_SEVERITY = "high"


@dataclass(frozen=True)
class Review:
    hypothesis_id: str
    decision: str
    reviewer: str
    at: datetime
    note: str = ""


def correlation_key(tenant_id: str, subject: str, incident_type: str, first_event_id: str) -> str:
    """Identidade do incidente. `subject` é o job em runtime e o ativo em qualidade."""
    raw = f"{tenant_id}|{subject}|{incident_type}|{first_event_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def open_or_update(
    open_incidents: list[Incident],
    tenant_id: str,
    subject: str,
    incident_type: str,
    run: Run,
) -> tuple[Incident, bool]:
    for incident in open_incidents:
        matches = (
            incident.tenant_id == tenant_id
            and incident.subject == subject
            and incident.type == incident_type
        )
        if matches and incident.is_active:
            return incident.touch(run), False

    key = correlation_key(tenant_id, subject, incident_type, run.run_id)
    incident = Incident(
        incident_id=stable_id("inc", key),
        correlation_key=key,
        tenant_id=tenant_id,
        subject=subject,
        type=incident_type,
        state="detected",
        severity=DEFAULT_SEVERITY,
        first_run_id=run.run_id,
        last_run_id=run.run_id,
        detected_at=run.end_time,
        updated_at=run.end_time,
    )
    return incident, True


def open_or_update_for_asset(
    open_incidents: list[Incident],
    tenant_id: str,
    asset: str,
    incident_type: str,
    first_result_id: str,
    at: datetime,
    severity: str = DEFAULT_SEVERITY,
) -> tuple[Incident, bool]:
    """Versão para qualidade: o assunto é o ativo e o evento é o resultado da regra."""
    for incident in open_incidents:
        matches = (
            incident.tenant_id == tenant_id
            and incident.subject == asset
            and incident.type == incident_type
        )
        if matches and incident.is_active:
            return incident.touch_at(first_result_id, at), False

    key = correlation_key(tenant_id, asset, incident_type, first_result_id)
    incident = Incident(
        incident_id=stable_id("inc", key),
        correlation_key=key,
        tenant_id=tenant_id,
        subject=asset,
        type=incident_type,
        state="detected",
        severity=severity,
        first_run_id=first_result_id,
        last_run_id=first_result_id,
        detected_at=at,
        updated_at=at,
    )
    return incident, True


def detection_entry(incident: Incident, run: Run, baseline: Baseline, created: bool) -> TimelineEntry:
    return TimelineEntry(
        entry_id=stable_id("tl", incident.incident_id, run.run_id),
        incident_id=incident.incident_id,
        at=run.end_time,
        kind="detected" if created else "recurrence",
        summary=detection_summary(run, baseline),
    )


def detection_summary(run: Run, baseline: Baseline) -> str:
    """Execução e duração total lado a lado, com a incerteza do baseline.

    A execução é o que decide; a duração total é o que o usuário esperou. Mostrar só uma
    esconderia ou o sinal (o setup domina a total) ou a experiência de quem aguardou.
    """
    medido = run.execution_s if baseline.metric == "execution" else run.duration_s
    fator = medido / baseline.median_s if baseline.median_s else 0.0
    partes = [
        f"Run {run.run_id}: {baseline.metric} {medido:.0f}s contra mediana {baseline.median_s:.0f}s "
        f"({fator:.1f}×); limiar {baseline.threshold_s:.0f}s pelo termo {baseline.deciding_term}",
        f"MAD {baseline.mad_s:.1f}s, n={baseline.n}",
    ]
    if baseline.metric == "execution":
        partes.append(f"duração total {run.duration_s:.0f}s (setup {run.setup_s or 0:.0f}s)")
    else:
        partes.append("sem tempo de execução medido: comparado pela duração total")
    if baseline.band is not None:
        partes.append(f"faixa de volume 2^{baseline.band}")
    elif baseline.band_fallback:
        partes.append("faixa de volume sem amostra: baseline do regime inteiro")
    return "; ".join(partes)


def apply_reviews(
    hypotheses: list[Hypothesis], reviews: list[Review]
) -> tuple[list[Hypothesis], list[TimelineEntry]]:
    by_hypothesis = {review.hypothesis_id: review for review in _latest_reviews(reviews)}
    updated: list[Hypothesis] = []
    entries: list[TimelineEntry] = []
    for hypothesis in hypotheses:
        review = by_hypothesis.get(hypothesis.hypothesis_id)
        if review is None:
            updated.append(hypothesis)
            continue
        if review.decision == "confirmed":
            updated.append(hypothesis.confirmed_by(review.reviewer, review.at))
        else:
            updated.append(hypothesis.rejected_by(review.reviewer, review.at))
        entries.append(
            TimelineEntry.create(
                incident_id=_incident_of(hypothesis),
                at=review.at,
                kind=f"hypothesis_{review.decision}",
                summary=f"{review.reviewer}: {hypothesis.statement}",
                actor=review.reviewer,
            )
        )
    return updated, entries


def _latest_reviews(reviews: list[Review]) -> list[Review]:
    latest: dict[str, Review] = {}
    for review in sorted(reviews, key=lambda item: item.at):
        latest[review.hypothesis_id] = review
    return list(latest.values())


def _incident_of(hypothesis: Hypothesis) -> str:
    return hypothesis.hypothesis_id.replace("hyp-", "inc-", 1)
