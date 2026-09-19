from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from eict.domain.models import AVAILABLE, NOT_AVAILABLE, PENDING, RunCost

BILLING_GRACE_PERIOD = timedelta(hours=24)


@dataclass(frozen=True)
class BillingFact:
    run_id: str
    dbus: float
    list_cost_usd: float
    source_ref: str


def incremental_cost(
    run_id: str,
    run_end: datetime,
    now: datetime,
    run_fact: BillingFact | None,
    baseline_facts: list[BillingFact],
    billing_available: bool = True,
) -> RunCost:
    if not billing_available:
        return RunCost(run_id=run_id, status=NOT_AVAILABLE)
    if run_fact is None:
        expired = now - run_end > BILLING_GRACE_PERIOD
        return RunCost(run_id=run_id, status=NOT_AVAILABLE if expired else PENDING)
    if not baseline_facts:
        return RunCost(
            run_id=run_id,
            status=AVAILABLE,
            dbus=run_fact.dbus,
            list_cost_usd=run_fact.list_cost_usd,
            source_ref=run_fact.source_ref,
        )
    baseline_cost = _median([fact.list_cost_usd for fact in baseline_facts])
    return RunCost(
        run_id=run_id,
        status=AVAILABLE,
        dbus=run_fact.dbus,
        list_cost_usd=run_fact.list_cost_usd,
        baseline_cost_usd=baseline_cost,
        incremental_cost_usd=round(run_fact.list_cost_usd - baseline_cost, 4),
        source_ref=run_fact.source_ref,
    )


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def utc_now() -> datetime:
    return datetime.now(UTC)
