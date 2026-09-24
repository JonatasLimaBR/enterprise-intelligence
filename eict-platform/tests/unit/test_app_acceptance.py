"""Aceite de regime no console (AT-07, AT-10, AT-11): validação e escritas, sem Streamlit."""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

import acceptance  # noqa: E402

from eict.domain.models import stable_id  # noqa: E402

NOW = datetime(2026, 9, 24, 12, tzinfo=UTC)
INICIO = datetime(2026, 9, 20, 0, 26, tzinfo=UTC)
INCIDENTE = {"incident_id": "inc-0c5d5ba2c700", "subject": "580618456320695"}


def _table(layer, name):
    return f"workspace.eict_{layer}.{name}"


def _escritas(email="ana@exemplo.com", motivo="lógica de janela nova é intencional"):
    return acceptance.statements(INCIDENTE, INICIO, email, motivo, NOW, _table)


def test_at10_tres_escritas_na_ordem():
    alvos = [re.search(r"workspace\.\S+", sql).group(0) for sql, _ in _escritas()]

    assert alvos == [
        "workspace.eict_ops.baseline_regimes",
        "workspace.eict_ops.incidents",
        "workspace.eict_ops.incident_timeline",
    ]


def test_at07_regime_comeca_no_primeiro_run_nao_no_clique():
    _, params = _escritas()[0]

    assert params["effective_from_at"] == INICIO
    assert params["created_at"] == NOW
    assert params["decided_by"] == "ana@exemplo.com"


def test_incidente_fecha_como_decisao_so_se_ativo():
    sql, params = _escritas()[1]

    assert "state = 'closed'" in sql
    assert "state IN ('detected'" in sql
    assert params["incident_id"] == INCIDENTE["incident_id"]


def test_timeline_registra_quem_e_por_que():
    _, params = _escritas()[2]

    assert params["actor"] == "ana@exemplo.com"
    assert "lógica de janela nova é intencional" in params["summary"]


def test_clicar_duas_vezes_nao_duplica():
    primeira, segunda = _escritas(), _escritas(email="bia@exemplo.com", motivo="outro")

    assert primeira[0][1]["regime_id"] == segunda[0][1]["regime_id"]
    assert primeira[2][1]["entry_id"] == segunda[2][1]["entry_id"]
    assert "WHEN NOT MATCHED" in primeira[0][0] and "WHEN NOT MATCHED" in primeira[2][0]


def test_id_do_regime_casa_com_o_do_pacote():
    assert acceptance.stable_id("reg", "a", "b") == stable_id("reg", "a", "b")


def test_at11_sem_justificativa_nada_e_gerado():
    assert acceptance.refusal("ana@exemplo.com", "   ") == "justificativa obrigatória"
    with pytest.raises(ValueError):
        _escritas(motivo="")


def test_sem_identidade_encaminhada_nada_e_gerado():
    assert "identidade" in acceptance.refusal(None, "motivo")
    with pytest.raises(ValueError, match="identidade"):
        _escritas(email="")


def test_valido_nao_tem_recusa():
    assert acceptance.refusal("ana@exemplo.com", "motivo") is None
