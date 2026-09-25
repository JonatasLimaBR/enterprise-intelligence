"""Papéis e autorização do console (AT-01…06, AT-11)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

import access  # noqa: E402
from access import (  # noqa: E402
    ACCEPT_REGIME,
    REVIEW_HYPOTHESIS,
    VIEW_AUDIT,
    Directory,
    RolesError,
    authorize,
    load_directory,
    parse_roles,
)

DIRETORIO = Directory(
    parse_roles(
        {
            "users": {
                "ana@exemplo.com": ["operador"],
                "bia@exemplo.com": ["engenheiro_dados"],
                "caio@exemplo.com": ["auditor"],
                "Duda@Exemplo.com": ["data_steward"],
            }
        }
    )
)


def test_at01_operador_confirma_hipotese():
    decisao = authorize(DIRETORIO, "ana@exemplo.com", REVIEW_HYPOTHESIS)

    assert decisao.allowed
    assert decisao.reason == "papel operador"


def test_at02_operador_nao_aceita_regime():
    decisao = authorize(DIRETORIO, "ana@exemplo.com", ACCEPT_REGIME)

    assert not decisao.allowed
    assert "operador não autorizam accept_regime" in decisao.reason


def test_at03_fora_do_arquivo_so_le():
    decisao = authorize(DIRETORIO, "intruso@exemplo.com", REVIEW_HYPOTHESIS)

    assert not decisao.allowed
    assert decisao.reason == "usuário sem papel: só leitura"


def test_at04_sem_identidade_nada_passa():
    decisao = authorize(DIRETORIO, None, REVIEW_HYPOTHESIS)

    assert not decisao.allowed
    assert decisao.actor == "desconhecido"


def test_at05_engenheiro_aceita_regime():
    assert authorize(DIRETORIO, "bia@exemplo.com", ACCEPT_REGIME).allowed


def test_at06_auditor_le_a_trilha_mas_nao_age():
    assert authorize(DIRETORIO, "caio@exemplo.com", VIEW_AUDIT).allowed
    assert not authorize(DIRETORIO, "caio@exemplo.com", REVIEW_HYPOTHESIS).allowed


def test_quem_age_nao_le_a_trilha():
    assert not authorize(DIRETORIO, "bia@exemplo.com", VIEW_AUDIT).allowed


def test_email_e_case_insensitive():
    assert authorize(DIRETORIO, "duda@exemplo.com", VIEW_AUDIT).allowed


def test_at11_papel_desconhecido_recusa_o_arquivo_inteiro():
    with pytest.raises(RolesError, match="papel desconhecido: admin"):
        parse_roles({"users": {"ana@exemplo.com": ["operador"], "x@exemplo.com": ["admin"]}})


def test_arquivo_invalido_deixa_todos_so_leitura(tmp_path):
    arquivo = tmp_path / "roles.yaml"
    arquivo.write_text("users:\n  ana@exemplo.com: [superusuario]\n", encoding="utf-8")

    diretorio = load_directory(arquivo)
    decisao = authorize(diretorio, "ana@exemplo.com", REVIEW_HYPOTHESIS)

    assert not decisao.allowed
    assert "modo só leitura" in decisao.reason


def test_arquivo_ausente_deixa_todos_so_leitura(tmp_path):
    assert load_directory(tmp_path / "nao_existe.yaml").by_email == {}


def test_lista_vazia_e_recusada():
    with pytest.raises(RolesError):
        parse_roles({"users": {"ana@exemplo.com": []}})


def test_arquivo_do_repositorio_e_valido():
    diretorio = load_directory(access.ROLES_FILE)

    assert diretorio.error == ""
    assert diretorio.by_email


def test_quem_decide_recomendacoes():
    from access import REVIEW_RECOMMENDATION

    assert authorize(DIRETORIO, "ana@exemplo.com", REVIEW_RECOMMENDATION).allowed       # operador
    assert authorize(DIRETORIO, "duda@exemplo.com", REVIEW_RECOMMENDATION).allowed      # data_steward
    assert not authorize(DIRETORIO, "caio@exemplo.com", REVIEW_RECOMMENDATION).allowed  # auditor só lê


def test_quem_gerencia_problemas():
    from access import MANAGE_PROBLEM

    assert authorize(DIRETORIO, "bia@exemplo.com", MANAGE_PROBLEM).allowed       # engenheiro_dados
    assert authorize(DIRETORIO, "duda@exemplo.com", MANAGE_PROBLEM).allowed      # data_steward
    assert not authorize(DIRETORIO, "ana@exemplo.com", MANAGE_PROBLEM).allowed   # operador
