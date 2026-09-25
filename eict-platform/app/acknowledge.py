"""Reconhecer um incidente: "alguém está olhando".

É o que o MTTA mede (SPEC-017: `acknowledged_at − detected_at`). Sem reconhecimento, o MTTA fica
não medido — nunca zero. Reconhecer um incidente `detected` o move para `triaged`; um incidente
já reconhecido não é reconhecido de novo (o primeiro reconhecimento é o que conta para o MTTA).

Puro: monta as instruções; o `app.py` executa.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

ACTIVE_STATES = ("detected", "triaged", "investigating", "mitigating", "monitoring")


def _stable_id(prefix: str, *parts: str) -> str:
    """Mesma fórmula de `eict.domain.models.stable_id`."""
    return f"{prefix}-{hashlib.sha256('|'.join(parts).encode()).hexdigest()[:12]}"


def can_acknowledge(incident: dict) -> bool:
    return incident.get("state") in ACTIVE_STATES and not incident.get("acknowledged_at")


def statements(incident: dict, email: str, now: datetime, table) -> list[tuple[str, dict]]:
    if not (email or "").strip():
        raise ValueError("identidade não encaminhada pelo Databricks Apps")
    incident_id = incident["incident_id"]
    ativos = ", ".join(f"'{state}'" for state in ACTIVE_STATES)
    return [
        (
            f"UPDATE {table('ops', 'incidents')} "
            "SET acknowledged_at = :now, acknowledged_by = :email, "
            "state = CASE WHEN state = 'detected' THEN 'triaged' ELSE state END, "
            "version = version + 1 "
            f"WHERE incident_id = :incident_id AND acknowledged_at IS NULL AND state IN ({ativos})",
            {"now": now, "email": email.strip(), "incident_id": incident_id},
        ),
        (
            f"MERGE INTO {table('ops', 'incident_timeline')} t "
            "USING (SELECT :entry_id AS entry_id) s ON t.entry_id = s.entry_id "
            "WHEN NOT MATCHED THEN INSERT (entry_id, incident_id, at, kind, summary, evidence_ids, actor) "
            "VALUES (:entry_id, :incident_id, :at, 'acknowledged', :summary, array(), :actor)",
            {
                "entry_id": _stable_id("tl", incident_id, "acknowledged"),
                "incident_id": incident_id,
                "at": now,
                "summary": f"reconhecido por {email.strip()}",
                "actor": email.strip(),
            },
        ),
    ]
