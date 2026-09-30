"""Domínio do advisor Jev: zonas cinzentas, allow-list e mapeamento em recomendação."""

from __future__ import annotations

from eict.domain.jev_advisor import (
    CONNECTOR_FIELDS,
    RUNBOOK_FIELDS,
    TRIAGE_FIELDS,
    Answer,
    connector_calls,
    recommendation_row,
    runbook_calls,
    to_recommendation,
    triage_calls,
)

POLICY = "jev-advisor-v1"


def _incident(sev, iid="inc-1"):
    return {"incident_id": iid, "type": "runtime_regression", "severity": sev,
            "impact_score": 1.2, "affected_assets": ["a", "b"], "escalated_from": "warning"}


def test_triage_so_zona_cinzenta():
    calls = triage_calls([_incident("warning"), _incident("high"), _incident("critical"), _incident("info")])
    assert [c.incident_id for c in calls] == ["inc-1", "inc-1"]  # só warning e high
    assert all(c.question["type"] == "noul" for c in calls)


def test_triage_state_so_allow_list():
    [call] = triage_calls([_incident("high")])
    assert set(call.state) == set(TRIAGE_FIELDS)


def test_connector_state_so_allow_list():
    [call] = connector_calls([{"connector": "github", "status": "degradado", "detail": "422", "extra": "x"}])
    assert set(call.state) == set(CONNECTOR_FIELDS)  # 'extra' não vaza
    assert call.question["type"] == "choice"


def test_runbook_exige_dois_candidatos():
    um = runbook_calls([{"incident_id": "i", "incident_type": "t", "cause": "c", "candidate_ids": ["RB-1"]}])
    dois = runbook_calls([{"incident_id": "i", "incident_type": "t", "cause": "c", "candidate_ids": ["RB-1", "RB-2"]}])
    assert um == []
    assert len(dois) == 1 and set(dois[0].state) == set(RUNBOOK_FIELDS)


def test_to_recommendation_abaixo_do_limiar_e_none():
    [call] = triage_calls([_incident("high")])
    assert to_recommendation(call, Answer("sim", 0.60), 0.70, POLICY) is None
    assert to_recommendation(call, None, 0.70, POLICY) is None


def test_to_recommendation_acima_do_limiar():
    [call] = triage_calls([_incident("high")])
    rec = to_recommendation(call, Answer("sim", 0.82), 0.70, POLICY)
    assert rec is not None
    assert rec.kind == "jev_triage"
    assert rec.evidence_ids == ()          # Jev não é evidência
    assert "Jev (IA)" in rec.text and "82%" in rec.text
    assert "Triagem, não veredito" in rec.text  # confiança ≠ precisão (ADR-022)
    assert rec.owner_role == "operador"


def test_recommendation_row_tem_os_campos_da_tabela():
    [call] = triage_calls([_incident("high")])
    row = recommendation_row(to_recommendation(call, Answer("sim", 0.90), 0.70, POLICY))
    assert set(row) == {
        "recommendation_id", "incident_id", "hypothesis_id", "kind", "text",
        "basis", "evidence_ids", "owner_role", "policy_version",
    }
    assert row["evidence_ids"] == []
