from __future__ import annotations

import json
from datetime import timedelta

from eict.domain.hypotheses import analyze
from eict.domain.incidents import RUNTIME_REGRESSION, open_or_update
from eict.domain.narrative import (
    FALLBACK_SOURCE,
    LLM_SOURCE,
    build_facts,
    build_prompt,
    narrate,
    validate_narrative,
)
from tests.conftest import BASE_TIME, JOB_ID, TENANT

NOW = BASE_TIME + timedelta(hours=8)


def _context(regressed_features, healthy_features, commit_b):
    analysis = analyze(regressed_features, healthy_features, [commit_b], NOW)
    incident, _ = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, regressed_features.run)
    facts = build_facts(list(analysis.evidence))
    return incident, list(analysis.hypotheses), facts


def test_valid_llm_output_is_accepted(regressed_features, healthy_features, commit_b):
    incident, hypotheses, facts = _context(regressed_features, healthy_features, commit_b)
    raw = json.dumps(
        {"sentences": [{"text": "Run lento por skew.", "evidence_ids": [facts[0].evidence_id]}]}
    )

    narrative = narrate(raw, incident, hypotheses, facts)

    assert narrative.source == LLM_SOURCE
    assert narrative.rejected_reason is None


def test_markdown_fences_are_stripped(regressed_features, healthy_features, commit_b):
    incident, hypotheses, facts = _context(regressed_features, healthy_features, commit_b)
    payload = json.dumps(
        {"sentences": [{"text": "Run lento por skew.", "evidence_ids": [facts[0].evidence_id]}]}
    )

    narrative = narrate(f"```json\n{payload}\n```", incident, hypotheses, facts)

    assert narrative.source == LLM_SOURCE


def test_at008_unknown_evidence_id_is_rejected(regressed_features, healthy_features, commit_b):
    incident, hypotheses, facts = _context(regressed_features, healthy_features, commit_b)
    raw = json.dumps({"sentences": [{"text": "Causa confirmada.", "evidence_ids": ["ev-hallucinated"]}]})

    narrative = narrate(raw, incident, hypotheses, facts)

    assert narrative.source == FALLBACK_SOURCE
    assert narrative.rejected_reason is not None
    assert "unknown_evidence" in narrative.rejected_reason


def test_at008_sentence_without_evidence_is_rejected(
    regressed_features, healthy_features, commit_b
):
    incident, hypotheses, facts = _context(regressed_features, healthy_features, commit_b)
    raw = json.dumps({"sentences": [{"text": "Sem evidência.", "evidence_ids": []}]})

    narrative = narrate(raw, incident, hypotheses, facts)

    assert narrative.source == FALLBACK_SOURCE
    assert narrative.rejected_reason.startswith("schema")


def test_at008_invalid_json_falls_back(regressed_features, healthy_features, commit_b):
    incident, hypotheses, facts = _context(regressed_features, healthy_features, commit_b)

    narrative = narrate("not json at all", incident, hypotheses, facts)

    assert narrative.source == FALLBACK_SOURCE
    assert narrative.rejected_reason is not None


def test_sc3_every_fallback_sentence_cites_known_evidence(
    regressed_features, healthy_features, commit_b
):
    incident, hypotheses, facts = _context(regressed_features, healthy_features, commit_b)
    allowed = {fact.evidence_id for fact in facts}

    narrative = narrate(None, incident, hypotheses, facts)

    assert narrative.sentences
    for sentence in narrative.sentences:
        assert sentence.evidence_ids
        assert set(sentence.evidence_ids) <= allowed


def test_prompt_lists_facts_and_hypotheses(regressed_features, healthy_features, commit_b):
    incident, hypotheses, facts = _context(regressed_features, healthy_features, commit_b)

    prompt = build_prompt(incident, hypotheses, facts)

    assert facts[0].evidence_id in prompt
    assert "hipóteses são hipóteses" in prompt.lower()


def test_validate_narrative_returns_model_when_ids_are_known():
    raw = json.dumps({"sentences": [{"text": "ok", "evidence_ids": ["ev-1"]}]})

    model, reason = validate_narrative(raw, {"ev-1"})

    assert reason is None
    assert model is not None
