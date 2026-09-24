"""Regime de baseline: marco por aceite, por declaração, e o que nunca cria marco."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from eict.domain.baseline import evaluate
from eict.domain.regimes import (
    CONSOLE,
    DECLARED,
    FORWARDED_HEADER,
    Regime,
    RegimeError,
    parse_declaration,
    regime_start,
)
from tests.conftest import BASE_TIME, JOB_ID, make_run

NOW = BASE_TIME + timedelta(days=2)
SHA_NOVO = "c" * 40


def _declaracao(**campos):
    base = {
        "job_id": JOB_ID,
        "effective_from": {"git_sha": SHA_NOVO},
        "owner": "dados@exemplo.com",
        "reason": "tabela reduzida recriada",
    }
    base.update(campos)
    return base


def test_at08_regime_por_sha_comeca_no_primeiro_run_do_commit():
    historia = [make_run(i, 30) for i in range(5)] + [
        make_run(i, 30, git_sha=SHA_NOVO) for i in range(5, 8)
    ]

    inicio = regime_start(JOB_ID, [parse_declaration(_declaracao())], historia)

    assert inicio == historia[5].start_time


def test_sha_abreviado_na_declaracao_casa():
    historia = [make_run(0, 30, git_sha=SHA_NOVO)]
    regime = parse_declaration(_declaracao(effective_from={"git_sha": SHA_NOVO[:7]}))

    assert regime_start(JOB_ID, [regime], historia) == historia[0].start_time


def test_sha_sem_run_e_marco_pendente():
    historia = [make_run(i, 30) for i in range(5)]

    assert regime_start(JOB_ID, [parse_declaration(_declaracao())], historia) is None


def test_marco_mais_recente_vence():
    antigo = parse_declaration(_declaracao(effective_from={"at": "2026-09-19T08:00:00Z"}))
    recente = parse_declaration(_declaracao(effective_from={"at": "2026-09-20T08:00:00Z"}))

    inicio = regime_start(JOB_ID, [recente, antigo], [])

    assert inicio == datetime(2026, 9, 20, 8, tzinfo=UTC)


def test_regime_de_outro_job_nao_vale():
    outro = parse_declaration(_declaracao(job_id="outro", effective_from={"at": "2026-09-20T08:00:00Z"}))

    assert regime_start(JOB_ID, [outro], []) is None


def test_at12_declaracao_sem_dono_e_recusada():
    with pytest.raises(RegimeError, match="owner"):
        parse_declaration(_declaracao(owner=""), "x.yaml")


def test_declaracao_sem_motivo_e_recusada():
    with pytest.raises(RegimeError, match="reason"):
        parse_declaration(_declaracao(reason=" "))


def test_declaracao_com_dois_marcos_e_recusada():
    with pytest.raises(RegimeError, match="exatamente um"):
        parse_declaration(_declaracao(effective_from={"git_sha": SHA_NOVO, "at": "2026-09-20"}))


def test_declaracao_sem_marco_e_recusada():
    with pytest.raises(RegimeError, match="exatamente um"):
        parse_declaration(_declaracao(effective_from={}))


def test_id_da_declaracao_e_estavel():
    assert parse_declaration(_declaracao()).regime_id == parse_declaration(_declaracao()).regime_id
    assert parse_declaration(_declaracao()).origin == DECLARED


def test_regime_aceito_torna_o_lento_o_novo_normal():
    """Depois do aceite, com 5 runs no regime novo, o nível lento não é mais regressão."""
    saudaveis = [replace(make_run(i, 150), execution_s=28.0) for i in range(6)]
    lentos = [replace(make_run(i, 1500), execution_s=1400.0 + i) for i in range(6, 11)]
    regime = Regime(
        regime_id="reg-x", job_id=JOB_ID, origin=CONSOLE, decided_by="ana@exemplo.com",
        reason="motivo", identity_source=FORWARDED_HEADER, effective_from_at=lentos[0].start_time,
    )
    atual = replace(make_run(11, 1520), execution_s=1420.0)

    inicio = regime_start(JOB_ID, [regime], saudaveis + lentos)
    sem = evaluate(atual, saudaveis + lentos)
    com = evaluate(atual, saudaveis + lentos, regime_start=inicio)

    assert sem.is_regression
    assert not com.is_regression
    assert com.baseline.n == 5
