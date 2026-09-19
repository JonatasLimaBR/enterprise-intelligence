from __future__ import annotations

from eict.domain.diff import (
    available_dimensions,
    changed_dimensions,
    diff_runs,
    new_plan_operators,
)
from eict.domain.models import NOT_AVAILABLE, RunFeatures
from tests.conftest import make_run


def test_sc6_diff_exposes_at_least_seven_available_dimensions(
    regressed_features, healthy_features
):
    rows = diff_runs(healthy_features, regressed_features)

    assert available_dimensions(rows) >= 7


def test_spill_and_gc_are_reported_as_not_available(regressed_features, healthy_features):
    rows = {row.dimension: row for row in diff_runs(healthy_features, regressed_features)}

    assert rows["spill_bytes"].current == NOT_AVAILABLE
    assert rows["gc_ms"].current == NOT_AVAILABLE
    assert rows["spill_bytes"].changed is False


def test_changed_dimensions_include_commit_and_skew(regressed_features, healthy_features):
    changed = changed_dimensions(diff_runs(healthy_features, regressed_features))

    assert "commit" in changed
    assert "skew_ratio" in changed
    assert "environment" not in changed


def test_missing_healthy_run_marks_every_healthy_value_not_available(regressed_features):
    rows = diff_runs(None, regressed_features)

    assert all(row.healthy == NOT_AVAILABLE for row in rows)
    assert all(row.changed is False for row in rows)


def test_missing_profile_degrades_only_profile_dimensions(healthy_features):
    run = make_run(7, duration_s=3420)
    rows = {row.dimension: row for row in diff_runs(healthy_features, RunFeatures(run=run))}

    assert rows["skew_ratio"].current == NOT_AVAILABLE
    assert rows["duration_s"].current == "3420"


def test_new_plan_operators_lists_only_additions(regressed_features, healthy_features):
    operators = new_plan_operators(healthy_features, regressed_features)

    assert "Window" in operators
    assert "SortMergeJoin" not in operators


def test_new_plan_operators_empty_without_healthy_profile(regressed_features):
    assert new_plan_operators(None, regressed_features) == ()
