"""Incidente gravado e relido é o mesmo incidente — campo por campo.

O `MERGE` usa `UPDATE SET *` sobre o schema inteiro da tabela: o campo que o loader esquece de
ler volta como nulo na próxima gravação. Foi assim que incidentes auto-resolvidos perdiam o raio
de impacto e o motivo da elevação. Este teste compara **todos** os campos do modelo, para o
próximo campo novo não repetir a história.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

from eict.adapters.store import incident_row, to_incident
from eict.config import Settings
from eict.domain.models import Incident
from eict.jobs import correlate

AGORA = datetime(2026, 9, 24, 22, tzinfo=UTC)

COMPLETO = Incident(
    incident_id="inc-1",
    correlation_key="k1",
    tenant_id="demo",
    subject="workspace.eict_workload.orders",
    type="contract_violation",
    state="triaged",
    severity="critical",
    first_run_id="r1",
    last_run_id="r2",
    detected_at=AGORA,
    updated_at=AGORA,
    affected_assets=("painel", "x"),
    ticket_refs=("EICT-1",),
    declared_consumers=("comercial",),
    impact_score=1.675,
    impact_policy_version="impact-v1",
    escalated_from="warning",
    escalation_reason="raio atinge consumo humano",
    acknowledged_at=AGORA,
    acknowledged_by="ana@exemplo.com",
    version=7,
)


def test_todo_campo_do_modelo_e_gravado():
    linha = incident_row(COMPLETO)

    assert {campo.name for campo in fields(Incident)} <= set(linha)


def test_ida_e_volta_preserva_todos_os_campos():
    assert to_incident(incident_row(COMPLETO)) == COMPLETO


def test_loader_do_correlator_preserva_impacto_e_reconhecimento(monkeypatch):
    """O bug: o loader não lia impact_score nem escalated_from, e a próxima gravação os zerava."""
    monkeypatch.setattr(correlate.store, "query", lambda spark, sql: [incident_row(COMPLETO)])

    [relido] = correlate.load_active_incidents(None, Settings())

    assert relido == COMPLETO
