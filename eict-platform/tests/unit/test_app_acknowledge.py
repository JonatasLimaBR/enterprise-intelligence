"""Reconhecimento de incidente no console."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

from access import ACKNOWLEDGE_INCIDENT, Directory, authorize, parse_roles  # noqa: E402
from acknowledge import can_acknowledge, statements  # noqa: E402

from eict.domain.models import stable_id  # noqa: E402

AGORA = datetime(2026, 9, 24, 23, tzinfo=UTC)
INCIDENTE = {"incident_id": "inc-1", "state": "detected", "acknowledged_at": None}


def _table(layer, name):
    return f"workspace.eict_{layer}.{name}"


def test_reconhecer_move_detected_para_triaged_so_uma_vez():
    sql, params = statements(INCIDENTE, "ana@exemplo.com", AGORA, _table)[0]

    assert "CASE WHEN state = 'detected' THEN 'triaged' ELSE state END" in sql
    assert "acknowledged_at IS NULL" in sql
    assert params["email"] == "ana@exemplo.com"


def test_timeline_registra_quem_reconheceu_com_id_estavel():
    _, params = statements(INCIDENTE, "ana@exemplo.com", AGORA, _table)[1]

    assert params["actor"] == "ana@exemplo.com"
    assert params["entry_id"] == stable_id("tl", "inc-1", "acknowledged")


def test_sem_identidade_nao_reconhece():
    with pytest.raises(ValueError):
        statements(INCIDENTE, "", AGORA, _table)


def test_so_ativo_e_nao_reconhecido_pode_ser_reconhecido():
    assert can_acknowledge(INCIDENTE)
    assert not can_acknowledge({**INCIDENTE, "acknowledged_at": AGORA})
    assert not can_acknowledge({**INCIDENTE, "state": "recovered"})


def test_papeis_que_reconhecem():
    diretorio = Directory(parse_roles({"users": {"op@x.com": ["operador"], "aud@x.com": ["auditor"]}}))

    assert authorize(diretorio, "op@x.com", ACKNOWLEDGE_INCIDENT).allowed
    assert not authorize(diretorio, "aud@x.com", ACKNOWLEDGE_INCIDENT).allowed
