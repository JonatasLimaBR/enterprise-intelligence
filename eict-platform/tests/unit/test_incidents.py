from __future__ import annotations

from datetime import timedelta

from eict.domain.baseline import Baseline
from eict.domain.incidents import (
    RUNTIME_REGRESSION,
    Review,
    apply_reviews,
    correlation_key,
    detection_entry,
    open_or_update,
)
from eict.domain.models import Hypothesis
from tests.conftest import BASE_TIME, JOB_ID, TENANT, make_run

BASELINE = Baseline(median_s=1230.0, mad_s=20.0, threshold_s=2460.0, deciding_term="ratio", n=7, metric="total")


def test_new_incident_created_when_none_is_active():
    run = make_run(7, duration_s=3420)

    incident, created = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, run)

    assert created is True
    assert incident.state == "detected"
    assert incident.first_run_id == run.run_id
    assert incident.correlation_key == correlation_key(
        TENANT, JOB_ID, RUNTIME_REGRESSION, run.run_id
    )


def test_at004_second_slow_run_updates_the_same_incident():
    first = make_run(7, duration_s=3420)
    second = make_run(8, duration_s=3500)
    incident, _ = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, first)

    updated, created = open_or_update([incident], TENANT, JOB_ID, RUNTIME_REGRESSION, second)

    assert created is False
    assert updated.correlation_key == incident.correlation_key
    assert updated.last_run_id == second.run_id
    assert updated.version == incident.version + 1


def test_closed_incident_does_not_absorb_new_run():
    first = make_run(7, duration_s=3420)
    incident, _ = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, first)
    closed = incident.__class__(**{**incident.__dict__, "state": "closed"})
    second = make_run(9, duration_s=3600)

    new_incident, created = open_or_update([closed], TENANT, JOB_ID, RUNTIME_REGRESSION, second)

    assert created is True
    assert new_incident.correlation_key != closed.correlation_key


def test_other_job_gets_its_own_incident():
    run = make_run(7, duration_s=3420)
    incident, _ = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, run)
    other = make_run(8, duration_s=3420)
    other = other.__class__(**{**other.__dict__, "job_id": "job-99"})

    _, created = open_or_update([incident], TENANT, "job-99", RUNTIME_REGRESSION, other)

    assert created is True


def test_detection_entry_describes_duration_against_baseline():
    run = make_run(7, duration_s=3420)
    incident, created = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, run)

    entry = detection_entry(incident, run, BASELINE, created)

    assert entry.kind == "detected"
    assert "3420" in entry.summary
    assert entry.incident_id == incident.incident_id


def test_recurrence_entry_is_marked_as_recurrence():
    first = make_run(7, duration_s=3420)
    incident, _ = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, first)
    second = make_run(8, duration_s=3500)
    updated, created = open_or_update([incident], TENANT, JOB_ID, RUNTIME_REGRESSION, second)

    entry = detection_entry(updated, second, BASELINE, created)

    assert entry.kind == "recurrence"


def test_at015_review_confirms_hypothesis_and_creates_timeline_entry():
    hypothesis = Hypothesis(
        hypothesis_id="hyp-abc123",
        code="skew_join_change",
        statement="Skew na chave do join",
        confidence=0.85,
        rank=1,
    )
    review = Review(
        hypothesis_id="hyp-abc123",
        decision="confirmed",
        reviewer="analyst@example.com",
        at=BASE_TIME + timedelta(hours=9),
    )

    updated, entries = apply_reviews([hypothesis], [review])

    assert updated[0].status == "confirmed"
    assert updated[0].reviewed_by == "analyst@example.com"
    assert updated[0].reviewed_at == review.at
    assert entries[0].kind == "hypothesis_confirmed"
    assert entries[0].actor == "analyst@example.com"


def test_latest_review_wins():
    hypothesis = Hypothesis(
        hypothesis_id="hyp-abc123",
        code="skew_join_change",
        statement="Skew na chave do join",
        confidence=0.85,
    )
    first = Review("hyp-abc123", "confirmed", "a@example.com", BASE_TIME)
    second = Review("hyp-abc123", "rejected", "b@example.com", BASE_TIME + timedelta(hours=1))

    updated, _ = apply_reviews([hypothesis], [first, second])

    assert updated[0].status == "rejected"
    assert updated[0].reviewed_by == "b@example.com"


def test_timeline_entry_is_stable_per_run_across_reprocessing():
    run = make_run(7, duration_s=3420)
    incident, created = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, run)

    first_pass = detection_entry(incident, run, BASELINE, created)
    second_pass = detection_entry(incident, run, BASELINE, False)

    assert first_pass.entry_id == second_pass.entry_id
    assert first_pass.kind == "detected"
    assert second_pass.kind == "recurrence"


def test_timeline_entries_differ_between_runs():
    first_run = make_run(7, duration_s=3420)
    second_run = make_run(8, duration_s=3500)
    incident, _ = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, first_run)

    assert (
        detection_entry(incident, first_run, BASELINE, True).entry_id
        != detection_entry(incident, second_run, BASELINE, False).entry_id
    )
