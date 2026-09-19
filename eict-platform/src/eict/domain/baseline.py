from __future__ import annotations

import statistics
from dataclasses import dataclass

from eict.domain.models import Run

MIN_SAMPLES = 5
REGRESSION_FACTOR = 1.5
INSUFFICIENT_BASELINE = "insufficient_baseline"


@dataclass(frozen=True)
class Baseline:
    p50_s: float
    p95_s: float
    n: int


@dataclass(frozen=True)
class RegressionVerdict:
    is_regression: bool
    baseline: Baseline | None
    reason: str | None = None


def compute_baseline(
    history: list[Run],
    before: Run,
    excluded_run_ids: frozenset[str] = frozenset(),
) -> Baseline | None:
    durations = sorted(
        run.duration_s
        for run in history
        if run.succeeded
        and run.run_id != before.run_id
        and run.end_time <= before.start_time
        and run.run_id not in excluded_run_ids
    )
    if len(durations) < MIN_SAMPLES:
        return None
    return Baseline(
        p50_s=statistics.median(durations),
        p95_s=_percentile(durations, 0.95),
        n=len(durations),
    )


def is_regression(run: Run, baseline: Baseline | None) -> bool:
    if baseline is None:
        return False
    return run.duration_s > baseline.p95_s * REGRESSION_FACTOR


def evaluate(
    run: Run,
    history: list[Run],
    excluded_run_ids: frozenset[str] = frozenset(),
) -> RegressionVerdict:
    baseline = compute_baseline(history, run, excluded_run_ids)
    if baseline is None:
        return RegressionVerdict(False, None, INSUFFICIENT_BASELINE)
    return RegressionVerdict(is_regression(run, baseline), baseline)


def last_healthy_run(history: list[Run], before: Run) -> Run | None:
    candidates = [
        run
        for run in history
        if run.succeeded and run.run_id != before.run_id and run.end_time <= before.start_time
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda run: run.end_time)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
