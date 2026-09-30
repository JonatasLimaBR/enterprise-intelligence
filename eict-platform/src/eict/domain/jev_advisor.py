"""Advisor Jev: monta as chamadas nas zonas cinzentas e mapeia a resposta em recomendação.

Puro. Cada builder produz `AdvisorCall` com um `state` contendo **só** os campos da allow-list (constante
neste módulo — uma config YAML não amplia o que sai). `to_recommendation` só grava acima do limiar; o Jev
recomenda, nunca autoriza, e nunca vira evidência (`evidence_ids` vazio).
"""

from __future__ import annotations

from dataclasses import dataclass

from eict.domain.models import stable_id
from eict.domain.recommendations import Recommendation

TRIAGE_SEVERITIES = frozenset({"warning", "high"})
TRIAGE_FIELDS = ("type", "severity", "impact_score", "asset_count", "reaches_human")
CONNECTOR_FIELDS = ("connector", "status", "detail")
RUNBOOK_FIELDS = ("incident_type", "cause", "candidate_ids")


@dataclass(frozen=True)
class Answer:
    value: str
    confidence: float


@dataclass(frozen=True)
class JevConfig:
    enabled: frozenset[str]
    threshold: float = 0.70


@dataclass(frozen=True)
class AdvisorCall:
    advisor: str
    incident_id: str
    owner_role: str
    kind: str
    state: dict
    question: dict


def _pick(source: dict, fields: tuple[str, ...]) -> dict:
    return {campo: source[campo] for campo in fields if campo in source}


def triage_calls(incidents: list[dict]) -> list[AdvisorCall]:
    calls: list[AdvisorCall] = []
    for inc in incidents:
        if inc.get("severity") not in TRIAGE_SEVERITIES:
            continue
        state = {
            "type": inc.get("type"),
            "severity": inc.get("severity"),
            "impact_score": float(inc.get("impact_score") or 0.0),
            "asset_count": len(inc.get("affected_assets") or ()),
            "reaches_human": bool(inc.get("escalated_from")),
        }
        calls.append(
            AdvisorCall(
                "triage", inc.get("incident_id") or "", "operador", "jev_triage",
                _pick(state, TRIAGE_FIELDS),
                {"type": "noul", "prompt": "Este incidente merece atenção humana imediata?"},
            )
        )
    return calls


def connector_calls(connectors: list[dict]) -> list[AdvisorCall]:
    calls: list[AdvisorCall] = []
    for row in connectors:
        state = {"connector": row.get("connector"), "status": row.get("status"), "detail": row.get("detail")}
        calls.append(
            AdvisorCall(
                "connector", "", "operador", "jev_connector",
                _pick(state, CONNECTOR_FIELDS),
                {"type": "choice", "prompt": "A falha é permanente ou transitória?",
                 "choices": ["permanente", "transitorio"]},
            )
        )
    return calls


def runbook_calls(tied: list[dict]) -> list[AdvisorCall]:
    calls: list[AdvisorCall] = []
    for row in tied:
        candidatos = list(row.get("candidate_ids") or ())
        if len(candidatos) < 2:
            continue
        state = {
            "incident_type": row.get("incident_type"),
            "cause": row.get("cause"),
            "candidate_ids": candidatos,
        }
        calls.append(
            AdvisorCall(
                "runbook", row.get("incident_id") or "", "engenheiro_dados", "jev_runbook",
                _pick(state, RUNBOOK_FIELDS),
                {"type": "choice", "prompt": "Qual runbook se aplica melhor?", "choices": candidatos},
            )
        )
    return calls


def to_recommendation(call: AdvisorCall, answer: Answer | None, threshold: float, policy: str) -> Recommendation | None:
    if answer is None or answer.confidence < threshold:
        return None
    pct = round(answer.confidence * 100)
    rec_id = stable_id("rec", "jev", call.advisor, call.incident_id, str(call.state.get("connector", "")))
    texto = f"Jev (IA) — {call.advisor}: '{answer.value}' (confiança {pct}%). Recomendação, não decisão."
    base = f"Jev advisor '{call.advisor}' · campos: {', '.join(sorted(call.state))}"
    return Recommendation(
        recommendation_id=rec_id,
        incident_id=call.incident_id,
        hypothesis_id="",
        kind=call.kind,
        text=texto,
        basis=base,
        evidence_ids=(),
        owner_role=call.owner_role,
        policy_version=policy,
    )


def recommendation_row(rec: Recommendation) -> dict:
    return {
        "recommendation_id": rec.recommendation_id,
        "incident_id": rec.incident_id or None,
        "hypothesis_id": rec.hypothesis_id or None,
        "kind": rec.kind,
        "text": rec.text,
        "basis": rec.basis,
        "evidence_ids": list(rec.evidence_ids),
        "owner_role": rec.owner_role,
        "policy_version": rec.policy_version,
    }
