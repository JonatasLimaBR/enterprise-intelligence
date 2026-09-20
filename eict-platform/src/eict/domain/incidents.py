from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from eict.domain.baseline import Baseline
from eict.domain.models import Hypothesis, Incident, Run, TimelineEntry, stable_id

RUNTIME_REGRESSION = "runtime_regression"
DEFAULT_SEVERITY = "high"


@dataclass(frozen=True)
class Review:
    hypothesis_id: str
    decision: str
    reviewer: str
    at: datetime
    note: str = ""


def correlation_key(tenant_id: str, job_id: str, incident_type: str, first_run_id: str) -> str:
    raw = f"{tenant_id}|{job_id}|{incident_type}|{first_run_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def open_or_update(
    open_incidents: list[Incident],
    tenant_id: str,
    job_id: str,
    incident_type: str,
    run: Run,
) -> tuple[Incident, bool]:
    for incident in open_incidents:
        matches = (
            incident.tenant_id == tenant_id
            and incident.job_id == job_id
            and incident.type == incident_type
        )
        if matches and incident.is_active:
            return incident.touch(run), False

    key = correlation_key(tenant_id, job_id, incident_type, run.run_id)
    incident = Incident(
        incident_id=stable_id("inc", key),
        correlation_key=key,
        tenant_id=tenant_id,
        job_id=job_id,
        type=incident_type,
        state="detected",
        severity=DEFAULT_SEVERITY,
        first_run_id=run.run_id,
        last_run_id=run.run_id,
        detected_at=run.end_time,
        updated_at=run.end_time,
    )
    return incident, True


def detection_entry(incident: Incident, run: Run, baseline: Baseline, created: bool) -> TimelineEntry:
    return TimelineEntry(
        entry_id=stable_id("tl", incident.incident_id, run.run_id),
        incident_id=incident.incident_id,
        at=run.end_time,
        kind="detected" if created else "recurrence",
        summary=(
            f"Run {run.run_id} levou {run.duration_s:.0f}s contra p95 de {baseline.p95_s:.0f}s "
            f"(baseline n={baseline.n})"
        ),
    )


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
