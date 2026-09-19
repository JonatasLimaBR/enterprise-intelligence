from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from eict.adapters import store
from eict.config import Settings, parse_settings
from eict.domain.envelope import Envelope, InvalidEnvelopeError
from eict.domain.incidents import RUNTIME_REGRESSION, open_or_update
from eict.domain.models import Evidence
from tests.conftest import make_run

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


def build_envelope(subject: str = "job/42/run/7") -> Envelope:
    return Envelope.create(
        source="databricks/demo",
        type="execution.completed",
        subject=subject,
        time=NOW,
        tenant_id="demo",
        data={"run_id": "7", "duration_s": 3420},
    )


def test_envelope_id_is_deterministic_for_the_same_observation():
    assert build_envelope().id == build_envelope().id
    assert build_envelope().id != build_envelope("job/42/run/8").id


def test_envelope_row_serializes_data_as_json():
    row = build_envelope().as_row()

    assert json.loads(row["data"])["run_id"] == "7"
    assert row["schema_version"] == 1
    assert row["content_hash"]


def test_unknown_event_type_is_rejected():
    with pytest.raises(InvalidEnvelopeError):
        Envelope.create("s", "execution.exploded", "subject", NOW, "demo", {})


def test_missing_subject_is_rejected():
    with pytest.raises(InvalidEnvelopeError):
        Envelope.create("s", "execution.completed", "", NOW, "demo", {})


def test_incident_row_flattens_tuples_into_lists():
    incident, _ = open_or_update([], "demo", "job-42", RUNTIME_REGRESSION, make_run(7, 3420))

    row = store.incident_row(incident.with_ticket("https://jira/EICT-1"))

    assert row["ticket_refs"] == ["https://jira/EICT-1"]
    assert row["affected_assets"] == []
    assert row["correlation_key"] == incident.correlation_key


def test_ticket_is_not_duplicated():
    incident, _ = open_or_update([], "demo", "job-42", RUNTIME_REGRESSION, make_run(7, 3420))

    once = incident.with_ticket("https://jira/EICT-1")
    twice = once.with_ticket("https://jira/EICT-1")

    assert twice.ticket_refs == ("https://jira/EICT-1",)
    assert twice.version == once.version


def test_evidence_row_keeps_hash_and_source():
    evidence = Evidence.create("data_skew", "run_profile/7", NOW, "skew de 18x", 18.0)

    row = store.evidence_row("inc-1", evidence)

    assert row["evidence_id"] == evidence.evidence_id
    assert row["hash"] == evidence.hash
    assert row["value_json"] == "18.0"


def test_run_roundtrip_through_store_mapping():
    run = make_run(7, duration_s=3420)

    record = {
        "run_id": run.run_id,
        "job_id": run.job_id,
        "start_time": run.start_time,
        "end_time": run.end_time,
        "duration_s": run.duration_s,
        "result_state": run.result_state,
        "git_sha": run.git_sha,
        "env_hash": run.env_hash,
        "input_rows": run.input_rows,
        "job_parameters": run.job_parameters,
    }

    assert store.to_run(record) == run


def test_run_profile_mapping_returns_none_without_skew_ratio():
    assert store.to_run_profile({"run_id": "7", "skew_ratio": None}) is None


def test_run_profile_mapping_builds_domain_object():
    record = json.loads(
        (__import__("pathlib").Path(__file__).resolve().parents[1] / "fixtures" / "run_profile.json").read_text(
            encoding="utf-8"
        )
    )

    profile = store.to_run_profile(record)

    assert profile is not None
    assert profile.hot_key == "C-000001"
    assert "Window" in profile.plan_operators


def test_settings_build_qualified_table_names():
    settings = Settings(catalog="workspace", schema_prefix="eict_")

    assert settings.table("ops", "incidents") == "workspace.eict_ops.incidents"
    assert settings.run_profiles_dir.endswith("/run_profiles")


def test_parse_settings_reads_job_parameters():
    settings = parse_settings(
        ["--catalog=main", "--schema-prefix=x_", "--llm-endpoint=databricks-gpt-oss-120b"]
    )

    assert settings.catalog == "main"
    assert settings.table("gold", "run_features") == "main.x_gold.run_features"
    assert settings.llm_endpoint == "databricks-gpt-oss-120b"
