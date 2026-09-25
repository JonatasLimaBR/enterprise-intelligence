"""Ações de economia no console: papéis, transições, congelamento e autoaprovação (AT-11…14, AT-20)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

from access import (  # noqa: E402
    APPROVE_SAVING,
    DISCARD_SAVING,
    IMPLEMENT_SAVING,
    Directory,
    authorize,
    load_directory,
)
from savings_actions import (  # noqa: E402
    SavingsActionError,
    approve,
    discard,
    implement,
    initiative_id,
)

AGORA = datetime(2026, 9, 25, 12, tzinfo=UTC)
OPORTUNIDADE = {
    "opportunity_id": "opp-1", "status": "identificada", "source": "regressao_custo", "subject": "1", "job_id": "1",
    "estimate_usd": Decimal("1.3640"), "estimate_low": Decimal("1.3640"), "estimate_high": Decimal("1.3640"),
    "formula": "f", "confidence": 0.9, "risk": "alto", "hypothesis_code": "skew_join_change",
    "unit": "custo incremental por run", "policy_version": "savings-v1",
}


def _table(layer, name):
    return f"cat.eict_{layer}.{name}"


def _diretorio(**papeis):
    return Directory({email: frozenset(lista) for email, lista in papeis.items()})


def test_at11_finops_aprova_e_congela_a_oportunidade():
    assert authorize(_diretorio(f=["finops"]), "f", APPROVE_SAVING).allowed
    [(sql, params)] = approve(OPORTUNIDADE, "f", AGORA, _table)
    assert "savings_initiatives" in sql and "WHEN NOT MATCHED THEN INSERT" in sql
    assert params["state"] == "aprovada" and params["approved_by"] == "f"
    assert params["estimate_usd"] == Decimal("1.3640") and params["hypothesis_code"] == "skew_join_change"
    assert params["initiative_id"] == initiative_id("opp-1")


def test_at12_operador_nao_aprova_e_engenheiro_nao_aprova():
    diretorio = _diretorio(o=["operador"], e=["engenheiro_dados"])
    assert not authorize(diretorio, "o", APPROVE_SAVING).allowed
    assert not authorize(diretorio, "e", APPROVE_SAVING).allowed
    assert not authorize(diretorio, "e", DISCARD_SAVING).allowed
    assert authorize(diretorio, "e", IMPLEMENT_SAVING).allowed


def test_finops_nao_implementa():
    assert not authorize(_diretorio(f=["finops"]), "f", IMPLEMENT_SAVING).allowed


def test_oportunidade_em_iniciativa_nao_e_aprovada_de_novo():
    with pytest.raises(SavingsActionError):
        approve({**OPORTUNIDADE, "status": "em_iniciativa"}, "f", AGORA, _table)


def test_at13_implementar_sem_aprovar_e_recusado():
    with pytest.raises(SavingsActionError, match="aprovada"):
        implement({"initiative_id": "ini", "state": "descartada"}, "e", "abc123", None, AGORA, _table)


def test_implementar_exige_commit_ou_pr():
    with pytest.raises(SavingsActionError, match="commit"):
        implement({"initiative_id": "ini", "state": "aprovada"}, "e", " ", None, AGORA, _table)


def test_at14_mesma_pessoa_aprova_e_implementa_fica_autoaprovada():
    [(sql, params)] = implement(
        {"initiative_id": "ini", "state": "aprovada", "approved_by": "demo@x"}, "demo@x", "9872c00", 0.5, AGORA, _table
    )
    assert params["self_approved"] is True
    assert "state = 'aprovada'" in sql
    [(_, outro)] = implement(
        {"initiative_id": "ini", "state": "aprovada", "approved_by": "f@x"}, "e@x", "9872c00", None, AGORA, _table
    )
    assert outro["self_approved"] is False and outro["cost"] is None


def test_at20_descartar_sem_motivo_e_recusado():
    with pytest.raises(SavingsActionError, match="motivo"):
        discard(OPORTUNIDADE, "f", "  ", AGORA, _table)
    [(_, params)] = discard(OPORTUNIDADE, "f", "custo aceito pelo negócio", AGORA, _table)
    assert params["state"] == "descartada" and params["discard_reason"] == "custo aceito pelo negócio"


def test_sem_identidade_nada_e_gravado():
    with pytest.raises(SavingsActionError, match="identidade"):
        approve(OPORTUNIDADE, "", AGORA, _table)


def test_custo_negativo_e_recusado():
    with pytest.raises(SavingsActionError):
        implement({"initiative_id": "ini", "state": "aprovada"}, "e", "abc", -1.0, AGORA, _table)


def test_roles_do_repositorio_dao_finops_a_demo():
    diretorio = load_directory()
    assert diretorio.error == ""
    assert authorize(diretorio, "creatorhubmedia01@gmail.com", APPROVE_SAVING).allowed
