from __future__ import annotations

from collections.abc import Callable

from eict.domain.models import NOT_AVAILABLE, DiffRow, RunFeatures

DIMENSIONS: tuple[tuple[str, Callable[[RunFeatures], object | None]], ...] = (
    ("commit", lambda features: features.run.git_sha),
    ("job_parameters", lambda features: _format_parameters(features)),
    ("environment", lambda features: features.run.env_hash),
    ("duration_s", lambda features: round(features.run.duration_s, 1)),
    ("input_rows", lambda features: features.run.input_rows),
    ("max_key_rows", lambda features: features.profile.max_key_rows if features.profile else None),
    ("median_key_rows", lambda features: features.profile.median_key_rows if features.profile else None),
    ("skew_ratio", lambda features: round(features.profile.skew_ratio, 2) if features.profile else None),
    ("top_key_share", lambda features: round(features.profile.top_key_share, 4) if features.profile else None),
    ("plan_operators", lambda features: ", ".join(features.plan_operators) or None),
    ("spill_bytes", lambda features: None),
    ("gc_ms", lambda features: None),
)


def diff_runs(healthy: RunFeatures | None, current: RunFeatures) -> tuple[DiffRow, ...]:
    rows = []
    for dimension, extract in DIMENSIONS:
        healthy_value = _render(extract(healthy)) if healthy is not None else NOT_AVAILABLE
        current_value = _render(extract(current))
        rows.append(
            DiffRow(
                dimension=dimension,
                healthy=healthy_value,
                current=current_value,
                changed=healthy_value != current_value
                and NOT_AVAILABLE not in (healthy_value, current_value),
            )
        )
    return tuple(rows)


def available_dimensions(rows: tuple[DiffRow, ...]) -> int:
    return sum(1 for row in rows if row.available)


def changed_dimensions(rows: tuple[DiffRow, ...]) -> tuple[str, ...]:
    return tuple(row.dimension for row in rows if row.changed)


def new_plan_operators(healthy: RunFeatures | None, current: RunFeatures) -> tuple[str, ...]:
    if healthy is None or healthy.profile is None or current.profile is None:
        return ()
    return tuple(sorted(set(current.plan_operators) - set(healthy.plan_operators)))


def _render(value: object | None) -> str:
    if value is None or value == "":
        return NOT_AVAILABLE
    return str(value)


def _format_parameters(features: RunFeatures) -> str | None:
    parameters = {
        key: value for key, value in features.run.job_parameters.items() if key != "run_id"
    }
    if not parameters:
        return None
    return ", ".join(f"{key}={value}" for key, value in sorted(parameters.items()))
