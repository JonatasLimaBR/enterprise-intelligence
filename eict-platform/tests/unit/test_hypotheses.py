from __future__ import annotations

from datetime import timedelta

from eict.domain.hypotheses import (
    MAX_INFERRED_CONFIDENCE,
    TEMPORAL_ONLY_CAP,
    analyze,
)
from eict.domain.models import RunFeatures
from tests.conftest import BASE_TIME, make_profile, make_run


def _analyze(current, healthy, changes):
    return analyze(current, healthy, changes, BASE_TIME + timedelta(hours=8))


def test_at005_skew_hypothesis_ranks_first(regressed_features, healthy_features, commit_b):
    analysis = _analyze(regressed_features, healthy_features, [commit_b])

    top = analysis.hypotheses[0]
    assert top.code == "skew_join_change"
    assert top.rank == 1
    assert len(top.supporting) >= 3
    assert top.confidence <= MAX_INFERRED_CONFIDENCE


def test_at005_skew_evidence_covers_data_plan_and_change(
    regressed_features, healthy_features, commit_b
):
    analysis = _analyze(regressed_features, healthy_features, [commit_b])
    by_id = {item.evidence_id: item for item in analysis.evidence}

    top = analysis.hypotheses[0]
    kinds = {by_id[evidence_id].kind for evidence_id in top.supporting}

    assert {"data_skew", "plan_operator", "change"} <= kinds


def test_at005_spill_and_gc_are_missing_evidence(
    regressed_features, healthy_features, commit_b
):
    analysis = _analyze(regressed_features, healthy_features, [commit_b])
    by_id = {item.evidence_id: item for item in analysis.evidence}

    top = analysis.hypotheses[0]
    missing_kinds = {by_id[evidence_id].kind for evidence_id in top.missing}

    assert "spill_gc" in missing_kinds


def test_at006_identical_environment_becomes_contradicting_evidence(
    regressed_features, healthy_features, commit_b
):
    analysis = _analyze(regressed_features, healthy_features, [commit_b])

    compute = next(item for item in analysis.hypotheses if item.code == "compute_change")
    skew = next(item for item in analysis.hypotheses if item.code == "skew_join_change")

    assert compute.contradicting
    assert not compute.supporting
    assert compute.rank > skew.rank


def test_at007_temporal_only_change_is_capped(
    regressed_features, healthy_features, unrelated_commit
):
    analysis = _analyze(regressed_features, healthy_features, [unrelated_commit])

    temporal = next(
        item for item in analysis.hypotheses if item.code == "change_temporal_only"
    )

    assert temporal.confidence <= TEMPORAL_ONLY_CAP
    assert temporal.missing


def test_volume_growth_wins_when_input_doubles(healthy_features, commit_b):
    run = make_run(7, duration_s=3420, input_rows=30_000_000)
    current = RunFeatures(run=run, profile=make_profile(run.run_id, skew_ratio=2.0))

    analysis = _analyze(current, healthy_features, [commit_b])
    volume = next(item for item in analysis.hypotheses if item.code == "volume_growth")

    assert volume.supporting
    assert volume.confidence >= 0.4


def test_environment_change_supports_compute_hypothesis(healthy_features, commit_b):
    run = make_run(7, duration_s=3420, env_hash="env-v3-performance")
    current = RunFeatures(run=run, profile=make_profile(run.run_id))

    analysis = _analyze(current, healthy_features, [commit_b])
    compute = next(item for item in analysis.hypotheses if item.code == "compute_change")

    assert compute.supporting
    assert compute.confidence >= 0.5


def test_missing_profile_records_missing_evidence(healthy_features, commit_b):
    run = make_run(7, duration_s=3420)
    current = RunFeatures(run=run, profile=None)

    analysis = _analyze(current, healthy_features, [commit_b])
    by_id = {item.evidence_id: item for item in analysis.evidence}
    skew = next(item for item in analysis.hypotheses if item.code == "skew_join_change")

    assert "run_profile" in {by_id[evidence_id].kind for evidence_id in skew.missing}


def test_no_hypothesis_reaches_certainty(regressed_features, healthy_features, commit_b):
    analysis = _analyze(regressed_features, healthy_features, [commit_b])

    assert all(item.confidence < 1.0 for item in analysis.hypotheses)
    assert all(item.status == "proposed" for item in analysis.hypotheses)


def test_scope_id_keeps_one_hypothesis_set_per_incident(
    regressed_features, healthy_features, commit_b
):
    first = analyze(regressed_features, healthy_features, [commit_b], BASE_TIME, scope_id="inc-1")
    run = make_run(9, duration_s=3600, git_sha=regressed_features.run.git_sha)
    second_features = RunFeatures(run=run, profile=make_profile(run.run_id, skew_ratio=18.0))
    second = analyze(second_features, healthy_features, [commit_b], BASE_TIME, scope_id="inc-1")

    assert [h.hypothesis_id for h in first.hypotheses] == [
        h.hypothesis_id for h in second.hypotheses
    ]


def test_without_scope_id_hypotheses_are_per_run(
    regressed_features, healthy_features, commit_b
):
    first = analyze(regressed_features, healthy_features, [commit_b], BASE_TIME)
    run = make_run(9, duration_s=3600)
    second = analyze(
        RunFeatures(run=run, profile=make_profile(run.run_id)),
        healthy_features,
        [commit_b],
        BASE_TIME,
    )

    assert first.hypotheses[0].hypothesis_id != second.hypotheses[0].hypothesis_id
