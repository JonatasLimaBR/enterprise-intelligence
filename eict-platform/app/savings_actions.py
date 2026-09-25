"""Aprovar, descartar e implementar uma oportunidade de economia.

A pessoa decide; o ciclo só propõe e mede. A aprovação **congela** a oportunidade na iniciativa —
estimativa, fórmula, confiança, risco, hipótese — para a iniciativa não depender de uma oportunidade
que o ciclo pode deixar de ver. Mesma pessoa aprovando e implementando é permitido e fica marcado
como autoaprovada.

Puro: valida e monta as instruções; o `app.py` executa (depois de autorizar e auditar).
"""

from __future__ import annotations

import hashlib
from datetime import datetime

IDENTIFICADA = "identificada"
APROVADA = "aprovada"
IMPLEMENTADA = "implementada"
DESCARTADA = "descartada"

FROZEN_FIELDS = (
    "opportunity_id", "source", "subject", "job_id", "estimate_usd", "estimate_low", "estimate_high", "formula",
    "confidence", "risk", "hypothesis_code", "unit", "policy_version",
)


class SavingsActionError(ValueError):
    """Transição inválida: nada é gravado."""


def _stable_id(prefix: str, *parts: str) -> str:
    """Mesma fórmula de `eict.domain.models.stable_id`."""
    return f"{prefix}-{hashlib.sha256('|'.join(parts).encode()).hexdigest()[:12]}"


def initiative_id(opportunity_id: str) -> str:
    return _stable_id("ini", opportunity_id)


def _actor(email: str) -> str:
    if not (email or "").strip():
        raise SavingsActionError("identidade não encaminhada pelo Databricks Apps")
    return email.strip()


def _insert(opportunity: dict, state: str, extra: dict, table) -> tuple[str, dict]:
    campos = {**{campo: opportunity.get(campo) for campo in FROZEN_FIELDS}, "state": state, **extra}
    campos["initiative_id"] = initiative_id(opportunity["opportunity_id"])
    colunas = ", ".join(campos)
    valores = ", ".join(f":{campo}" for campo in campos)
    return (
        f"MERGE INTO {table('ops', 'savings_initiatives')} t "
        "USING (SELECT :initiative_id AS initiative_id) s ON t.initiative_id = s.initiative_id "
        f"WHEN NOT MATCHED THEN INSERT ({colunas}) VALUES ({valores})",
        campos,
    )


def approve(opportunity: dict, email: str, now: datetime, table) -> list[tuple[str, dict]]:
    if opportunity.get("status") != IDENTIFICADA:
        raise SavingsActionError(f"só oportunidade identificada é aprovada (esta está {opportunity.get('status')})")
    return [_insert(opportunity, APROVADA, {"approved_by": _actor(email), "approved_at": now}, table)]


def discard(opportunity: dict, email: str, reason: str, now: datetime, table) -> list[tuple[str, dict]]:
    if opportunity.get("status") != IDENTIFICADA:
        raise SavingsActionError(f"só oportunidade identificada é descartada (esta está {opportunity.get('status')})")
    if not (reason or "").strip():
        raise SavingsActionError("descartar exige motivo")
    extra = {"discarded_by": _actor(email), "discarded_at": now, "discard_reason": reason.strip()}
    return [_insert(opportunity, DESCARTADA, extra, table)]


def implement(
    initiative: dict, email: str, change_ref: str, cost_usd: float | None, now: datetime, table
) -> list[tuple[str, dict]]:
    if initiative.get("state") != APROVADA:
        raise SavingsActionError(f"só iniciativa aprovada é implementada (esta está {initiative.get('state')})")
    if not (change_ref or "").strip():
        raise SavingsActionError("implementar exige o commit ou o link do PR")
    if cost_usd is not None and cost_usd < 0:
        raise SavingsActionError("custo de implementação não pode ser negativo")
    ator = _actor(email)
    return [
        (
            f"UPDATE {table('ops', 'savings_initiatives')} "
            "SET state = 'implementada', implemented_by = :actor, implemented_at = :now, change_ref = :change_ref, "
            "implementation_cost_usd = :cost, self_approved = :self_approved "
            "WHERE initiative_id = :initiative_id AND state = 'aprovada'",
            {
                "actor": ator,
                "now": now,
                "change_ref": change_ref.strip(),
                "cost": cost_usd,
                "self_approved": ator == initiative.get("approved_by"),
                "initiative_id": initiative["initiative_id"],
            },
        )
    ]
