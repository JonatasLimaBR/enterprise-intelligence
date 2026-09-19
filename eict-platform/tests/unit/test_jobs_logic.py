from __future__ import annotations

import json
from datetime import timedelta

from eict.adapters.llm import NarratorResponse
from eict.config import Settings
from eict.domain.hypotheses import analyze
from eict.domain.incidents import RUNTIME_REGRESSION, open_or_update
from eict.jobs.collect import change_envelope, run_envelope
from eict.jobs.correlate import changes_in_window
from eict.jobs.narrate import narrate_incident
from tests.conftest import BASE_TIME

SETTINGS = Settings()
NOW = BASE_TIME + timedelta(hours=8)


class _Client:
    def __init__(self, content):
        self.content = content
        self.prompts: list[str] = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return NarratorResponse(content=self.content, model="test-endpoint", trace_id="tr-1")


def _incident_context(regressed_features, healthy_features, commit_b):
    analysis = analyze(regressed_features, healthy_features, [commit_b], NOW)
    incident, _ = open_or_update(
        [], SETTINGS.tenant_id, "job-42", RUNTIME_REGRESSION, regressed_features.run
    )
    return incident, list(analysis.hypotheses), list(analysis.evidence)


def test_run_envelope_carries_git_sha_and_subject(regressed_features):
    envelope = run_envelope(regressed_features.run, SETTINGS, "databricks/demo")

    assert envelope.type == "execution.completed"
    assert envelope.subject.endswith(regressed_features.run.run_id)
    assert envelope.data["git_sha"] == regressed_features.run.git_sha


def test_change_envelope_subject_is_the_commit(commit_b):
    envelope = change_envelope(commit_b, SETTINGS, "databricks/demo")

    assert envelope.subject == f"commit/{commit_b.sha}"
    assert envelope.data["files"] == list(commit_b.files)


def test_deployed_commit_is_always_first_in_the_causal_window(
    regressed_features, healthy_features, commit_b, unrelated_commit
):
    ordered = changes_in_window([unrelated_commit, commit_b], healthy_features, regressed_features)

    assert ordered[0].sha == regressed_features.run.git_sha


def test_changes_outside_the_window_are_dropped(
    regressed_features, healthy_features, unrelated_commit
):
    stale = unrelated_commit.__class__(
        **{**unrelated_commit.__dict__, "committed_at": BASE_TIME - timedelta(days=30)}
    )

    ordered = changes_in_window([stale], healthy_features, regressed_features)

    assert ordered == []


def test_narrate_incident_uses_llm_when_output_is_valid(
    regressed_features, healthy_features, commit_b
):
    incident, hypotheses, evidence = _incident_context(
        regressed_features, healthy_features, commit_b
    )
    payload = json.dumps(
        {"sentences": [{"text": "Skew detectado.", "evidence_ids": [evidence[0].evidence_id]}]}
    )

    row = narrate_incident(_Client(payload), incident, hypotheses, evidence)

    assert row["source"] == "llm"
    assert row["model"] == "test-endpoint"
    assert row["rejected_reason"] is None


def test_narrate_incident_falls_back_and_records_reason(
    regressed_features, healthy_features, commit_b
):
    incident, hypotheses, evidence = _incident_context(
        regressed_features, healthy_features, commit_b
    )
    payload = json.dumps({"sentences": [{"text": "Causa!", "evidence_ids": ["ev-fake"]}]})

    row = narrate_incident(_Client(payload), incident, hypotheses, evidence)
    sentences = json.loads(row["sentences_json"])

    assert row["source"] == "fallback"
    assert "unknown_evidence" in row["rejected_reason"]
    assert sentences
    assert all(sentence["evidence_ids"] for sentence in sentences)


def test_narrate_incident_without_client_uses_fallback(
    regressed_features, healthy_features, commit_b
):
    incident, hypotheses, evidence = _incident_context(
        regressed_features, healthy_features, commit_b
    )

    row = narrate_incident(None, incident, hypotheses, evidence)

    assert row["source"] == "fallback"
    assert row["model"] is None


def test_narrative_id_changes_with_incident_version(
    regressed_features, healthy_features, commit_b
):
    incident, hypotheses, evidence = _incident_context(
        regressed_features, healthy_features, commit_b
    )
    bumped = incident.touch(regressed_features.run)

    first = narrate_incident(None, incident, hypotheses, evidence)["narrative_id"]
    second = narrate_incident(None, bumped, hypotheses, evidence)["narrative_id"]

    assert first != second
