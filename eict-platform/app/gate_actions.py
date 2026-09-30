"""Gate efetivo e escrita do override — no App, porque o console não importa `eict`.

`effective_outcome` é puro (decisão da policy + overrides + expiração). `override_statement` monta o INSERT
que o `app.py` executa sob `guarded()` (autorizado e auditado). Motivo obrigatório é validado no `app.py`
antes de chamar.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

PERMITE = "permite"
APROVADO = "aprovado"
DEFAULT_TTL_DAYS = 7


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"{prefix}-{digest[:12]}"


def effective_outcome(decision_outcome: str, overrides: list[dict], now: datetime) -> str:
    """Desfecho da policy, salvo override APROVADO e não expirado, que libera."""
    for override in overrides:
        expires = override.get("expires_at")
        if override.get("decision") == APROVADO and expires is not None and expires > now:
            return PERMITE
    return decision_outcome


def override_statement(
    sha: str, decision: str, reason: str, ticket: str, reviewer: str, now: datetime, table,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> tuple[str, dict]:
    override_id = _stable_id("gov", sha, reviewer, now.isoformat())
    statement = (
        f"INSERT INTO {table('ops', 'gate_overrides')} "
        "(override_id, sha, decision, reason, ticket, reviewer, created_at, expires_at) "
        "VALUES (:override_id, :sha, :decision, :reason, :ticket, :reviewer, :created_at, :expires_at)"
    )
    params = {
        "override_id": override_id,
        "sha": sha,
        "decision": decision,
        "reason": reason,
        "ticket": ticket or "",
        "reviewer": reviewer or "",
        "created_at": now,
        "expires_at": now + timedelta(days=ttl_days),
    }
    return statement, params
