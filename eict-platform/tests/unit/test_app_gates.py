"""Gate no App: `effective_outcome` (override/expiração) e RBAC `override_gate`."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

import gate_actions  # noqa: E402
from access import DATA_STEWARD, ENGENHEIRO_DADOS, OPERADOR, OVERRIDE_GATE, Directory, can  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _override(decision, dias):
    return {"decision": decision, "expires_at": NOW + timedelta(days=dias)}


def test_sem_override_mantem_decisao():
    assert gate_actions.effective_outcome("bloqueado", [], NOW) == "bloqueado"


def test_override_aprovado_valido_libera():
    assert gate_actions.effective_outcome("bloqueado", [_override("aprovado", 3)], NOW) == "permite"


def test_override_expirado_nao_libera():
    assert gate_actions.effective_outcome("bloqueado", [_override("aprovado", -1)], NOW) == "bloqueado"


def test_override_rejeitado_nao_libera():
    assert gate_actions.effective_outcome("bloqueado", [_override("rejeitado", 3)], NOW) == "bloqueado"


def test_override_statement_monta_insert_com_expiracao():
    stmt, params = gate_actions.override_statement(
        "c1", "aprovado", "motivo x", "TCK-1", "eng@x", NOW, lambda layer, name: f"ops.{name}"
    )
    assert "INSERT INTO ops.gate_overrides" in stmt
    assert params["sha"] == "c1" and params["decision"] == "aprovado" and params["reason"] == "motivo x"
    assert params["expires_at"] == NOW + timedelta(days=7)


def test_rbac_override_gate():
    diretorio = Directory(by_email={
        "eng@x": frozenset({ENGENHEIRO_DADOS}),
        "stew@x": frozenset({DATA_STEWARD}),
        "op@x": frozenset({OPERADOR}),
    })
    assert can(diretorio, "eng@x", OVERRIDE_GATE) is True
    assert can(diretorio, "stew@x", OVERRIDE_GATE) is True
    assert can(diretorio, "op@x", OVERRIDE_GATE) is False
