"""Aceite de um regime novo de runtime pelo console: "este nível é o novo normal".

Vive no app porque o app é publicado sem o pacote `eict`. É puro — valida e monta as
instruções SQL — para ser testado sem Streamlit nem warehouse.

A identidade vem do cabeçalho que o Databricks Apps encaminha com o usuário autenticado, nunca
de um campo digitado: o produto exige atribuição com proveniência verificável.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

IDENTITY_HEADER = "X-Forwarded-Email"
ACTIVE_STATES = ("detected", "triaged", "investigating", "mitigating", "monitoring")


def stable_id(prefix: str, *parts: str) -> str:
    """Mesma fórmula de `eict.domain.models.stable_id` — o id precisa casar com o do ciclo."""
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"{prefix}-{digest[:12]}"


def refusal(email: str | None, reason: str | None) -> str | None:
    """Motivo da recusa, ou `None` quando o aceite pode seguir."""
    if not (email or "").strip():
        return "identidade não encaminhada pelo Databricks Apps: aceite indisponível"
    if not (reason or "").strip():
        return "justificativa obrigatória"
    return None


def statements(
    incident: dict, first_run_start: datetime, email: str, reason: str, now: datetime, table
) -> list[tuple[str, dict]]:
    """Três escritas, na ordem: regime, incidente, timeline.

    O regime começa no início do 1º run do incidente — na mudança, não no clique. Tudo é
    idempotente: clicar duas vezes não duplica o regime, não reabre nem refecha o incidente,
    e a entrada de timeline tem id estável.
    """
    recusa = refusal(email, reason)
    if recusa:
        raise ValueError(recusa)
    email, reason = email.strip(), reason.strip()
    incident_id = incident["incident_id"]
    regime_id = stable_id("reg", incident["subject"], "console", incident_id)
    ativos = ", ".join(f"'{state}'" for state in ACTIVE_STATES)
    return [
        (
            f"MERGE INTO {table('ops', 'baseline_regimes')} t "
            "USING (SELECT :regime_id AS regime_id) s ON t.regime_id = s.regime_id "
            "WHEN NOT MATCHED THEN INSERT (regime_id, job_id, effective_from_at, effective_from_sha, "
            "origin, decided_by, identity_source, reason, incident_id, created_at) "
            "VALUES (:regime_id, :job_id, :effective_from_at, NULL, 'console', :decided_by, "
            "'forwarded_header', :reason, :incident_id, :created_at)",
            {
                "regime_id": regime_id,
                "job_id": incident["subject"],
                "effective_from_at": first_run_start,
                "decided_by": email,
                "reason": reason,
                "incident_id": incident_id,
                "created_at": now,
            },
        ),
        (
            f"UPDATE {table('ops', 'incidents')} "
            "SET state = 'closed', updated_at = :now, version = version + 1 "
            f"WHERE incident_id = :incident_id AND state IN ({ativos})",
            {"now": now, "incident_id": incident_id},
        ),
        (
            f"MERGE INTO {table('ops', 'incident_timeline')} t "
            "USING (SELECT :entry_id AS entry_id) s ON t.entry_id = s.entry_id "
            "WHEN NOT MATCHED THEN INSERT (entry_id, incident_id, at, kind, summary, evidence_ids, actor) "
            "VALUES (:entry_id, :incident_id, :at, 'regime_accepted', :summary, array(), :actor)",
            {
                "entry_id": stable_id("tl", incident_id, "regime_accepted"),
                "incident_id": incident_id,
                "at": now,
                "summary": (
                    f"aceito como novo normal por {email}: {reason}. "
                    f"Regime vale a partir de {first_run_start:%Y-%m-%d %H:%M} UTC"
                ),
                "actor": email,
            },
        ),
    ]
