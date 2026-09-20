from __future__ import annotations

from eict.domain.baseline import (
    INSUFFICIENT_BASELINE,
    compute_baseline,
    evaluate,
    is_regression,
    last_healthy_run,
)
from tests.conftest import make_run


def test_at001_regression_detected_above_p95_factor(healthy_history):
    regressed = make_run(8, duration_s=3420)

    verdict = evaluate(regressed, healthy_history)

    assert verdict.is_regression is True
    assert verdict.baseline is not None
    assert verdict.baseline.n == 7


def test_at002_insufficient_baseline_yields_no_incident():
    history = [make_run(index, duration_s=1200) for index in range(3)]
    regressed = make_run(4, duration_s=3420)

    verdict = evaluate(regressed, history)

    assert verdict.is_regression is False
    assert verdict.reason == INSUFFICIENT_BASELINE


def test_at003_failed_runs_excluded_from_baseline(healthy_history):
    polluted = [*healthy_history, make_run(7, duration_s=9000, result_state="FAILED")]
    current = make_run(8, duration_s=1800)

    baseline = compute_baseline(polluted, current)

    assert baseline is not None
    assert baseline.n == 7
    assert baseline.p95_s < 1400


def test_baseline_ignores_runs_after_the_evaluated_run(healthy_history):
    current = make_run(3, duration_s=3000)

    baseline = compute_baseline(healthy_history, current)

    assert baseline is None


def test_excluded_run_ids_are_dropped(healthy_history):
    current = make_run(8, duration_s=1800)

    kept = compute_baseline(healthy_history, current, frozenset({"run-0", "run-1"}))
    dropped_below_minimum = compute_baseline(
        healthy_history, current, frozenset({"run-0", "run-1", "run-2"})
    )

    assert kept is not None
    assert kept.n == 5
    assert dropped_below_minimum is None


def test_is_regression_without_baseline_is_false():
    assert is_regression(make_run(1, duration_s=9999), None) is False


def test_last_healthy_run_returns_latest_successful(healthy_history):
    current = make_run(8, duration_s=3420)

    healthy = last_healthy_run(healthy_history, current)

    assert healthy is not None
    assert healthy.run_id == "run-6"


def test_last_healthy_run_skips_runs_attributed_to_an_incident(healthy_history):
    regressed_first = make_run(7, duration_s=3420)
    history = [*healthy_history, regressed_first]
    current = make_run(8, duration_s=3500)

    naive = last_healthy_run(history, current)
    aware = last_healthy_run(history, current, frozenset({regressed_first.run_id}))

    assert naive is not None and naive.run_id == regressed_first.run_id
    assert aware is not None and aware.run_id == "run-6"
