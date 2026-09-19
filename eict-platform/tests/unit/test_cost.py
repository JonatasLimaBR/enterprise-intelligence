from __future__ import annotations

from datetime import timedelta

from eict.domain.cost import BillingFact, incremental_cost
from eict.domain.models import AVAILABLE, NOT_AVAILABLE, PENDING
from tests.conftest import BASE_TIME

RUN_END = BASE_TIME + timedelta(hours=8)
BASELINE_FACTS = [
    BillingFact("run-4", 0.9, 0.27, "system.billing.usage"),
    BillingFact("run-5", 1.0, 0.30, "system.billing.usage"),
    BillingFact("run-6", 1.1, 0.33, "system.billing.usage"),
]


def test_at009_cost_is_pending_while_billing_has_not_arrived():
    cost = incremental_cost("run-7", RUN_END, RUN_END + timedelta(minutes=10), None, BASELINE_FACTS)

    assert cost.status == PENDING
    assert cost.list_cost_usd is None


def test_at010_incremental_cost_uses_baseline_median():
    fact = BillingFact("run-7", 3.0, 0.90, "system.billing.usage")

    cost = incremental_cost("run-7", RUN_END, RUN_END + timedelta(hours=3), fact, BASELINE_FACTS)

    assert cost.status == AVAILABLE
    assert cost.baseline_cost_usd == 0.30
    assert cost.incremental_cost_usd == 0.60
    assert cost.source_ref == "system.billing.usage"


def test_sc8_billing_without_access_is_not_available():
    fact = BillingFact("run-7", 3.0, 0.90, "system.billing.usage")

    cost = incremental_cost(
        "run-7", RUN_END, RUN_END + timedelta(hours=3), fact, BASELINE_FACTS, billing_available=False
    )

    assert cost.status == NOT_AVAILABLE
    assert cost.list_cost_usd is None


def test_pending_expires_into_not_available_after_grace_period():
    cost = incremental_cost("run-7", RUN_END, RUN_END + timedelta(hours=25), None, BASELINE_FACTS)

    assert cost.status == NOT_AVAILABLE


def test_without_baseline_facts_only_absolute_cost_is_reported():
    fact = BillingFact("run-7", 3.0, 0.90, "system.billing.usage")

    cost = incremental_cost("run-7", RUN_END, RUN_END + timedelta(hours=3), fact, [])

    assert cost.status == AVAILABLE
    assert cost.incremental_cost_usd is None
    assert cost.list_cost_usd == 0.90
