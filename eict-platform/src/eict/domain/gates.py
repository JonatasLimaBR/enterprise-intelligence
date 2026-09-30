"""Gate de mudança: a policy determinística decide permite/requer_aprovacao/bloqueado.

Puro, usado pelo estágio `gates`. Precedência fixa (segredo alta → dependência alta → change risk alto →
default), primeira que casa. O cálculo do gate *efetivo* (com override/expiração) mora em `app/` porque o
App não importa `eict`.
"""

from __future__ import annotations

from dataclasses import dataclass

PERMITE = "permite"
APROVACAO = "requer_aprovacao"
BLOQUEADO = "bloqueado"


@dataclass(frozen=True)
class GatePolicy:
    secret_high: str = BLOQUEADO
    dependency_high: str = BLOQUEADO
    band_alto: str = APROVACAO
    default: str = PERMITE


@dataclass(frozen=True)
class GateDecision:
    sha: str
    outcome: str
    rule: str
    reason: str


def _has_high(findings: list[dict]) -> bool:
    return any(finding.get("severity") == "alta" for finding in findings)


def evaluate(
    change_risk: dict,
    secret_findings: list[dict],
    dep_findings: list[dict],
    policy: GatePolicy,
) -> GateDecision:
    sha = change_risk.get("sha", "")
    if _has_high(secret_findings):
        return GateDecision(sha, policy.secret_high, "segredo_alta", "segredo de alta severidade (SPEC-009)")
    if _has_high(dep_findings):
        return GateDecision(
            sha, policy.dependency_high, "dependencia_alta", "dependência vulnerável de alta severidade (SPEC-009)"
        )
    if change_risk.get("band") == "alto":
        return GateDecision(sha, policy.band_alto, "band_alto", "change risk alto (SPEC-009 alto risco)")
    return GateDecision(sha, policy.default, "sem_gatilho", "sem gatilho de gate")
