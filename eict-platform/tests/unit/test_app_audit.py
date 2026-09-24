"""Cadeia de hash da trilha de auditoria (AT-07…10, AT-12)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

from audit import (  # noqa: E402
    ADULTERADA,
    BIFURCADA,
    GENESIS,
    INTEGRA,
    entry,
    row_hash,
    verify,
)

INICIO = datetime(2026, 9, 24, 20, 0, tzinfo=UTC)


def _cadeia(n=4):
    linhas, ultima = [], None
    for i in range(n):
        ultima = entry(
            ultima,
            INICIO + timedelta(minutes=i),
            "ana@exemplo.com",
            frozenset({"operador"}),
            "review_hypothesis",
            f"hyp-{i}",
            "allowed",
            "papel operador",
        )
        linhas.append(ultima)
    return linhas


def test_primeira_linha_parte_da_genese():
    primeira = _cadeia(1)[0]

    assert primeira["seq"] == 1
    assert primeira["prev_hash"] == GENESIS


def test_at07_cadeia_integra():
    assert verify(_cadeia()).status == INTEGRA


def test_at08_motivo_editado_e_adulteracao():
    linhas = _cadeia()
    linhas[2] = {**linhas[2], "reason": "papel auditor"}

    veredito = verify(linhas)

    assert veredito.status == ADULTERADA
    assert veredito.first_bad_seq == 3
    assert "hash não confere" in veredito.detail


def test_editar_e_recalcular_o_hash_quebra_a_linha_seguinte():
    """Quem edita e recalcula o próprio hash deixa a próxima linha apontando para o nada."""
    linhas = _cadeia()
    editada = {**linhas[1], "decision": "denied"}
    editada["hash"] = row_hash(editada, editada["prev_hash"])
    linhas[1] = editada

    veredito = verify(linhas)

    assert veredito.status == ADULTERADA
    assert veredito.first_bad_seq == 3


def test_at09_linha_apagada_e_adulteracao():
    linhas = _cadeia()
    del linhas[1]

    veredito = verify(linhas)

    assert veredito.status == ADULTERADA
    assert veredito.first_bad_seq == 3
    assert "não existe" in veredito.detail


def test_at10_escrita_concorrente_e_bifurcacao_nao_adulteracao():
    base = _cadeia(2)
    ultima = base[-1]
    uma = entry(ultima, INICIO + timedelta(minutes=5), "ana@exemplo.com", frozenset({"operador"}),
                "review_hypothesis", "hyp-a", "allowed", "papel operador")
    outra = entry(ultima, INICIO + timedelta(minutes=5), "bia@exemplo.com", frozenset({"engenheiro_dados"}),
                  "accept_regime", "inc-1", "allowed", "papel engenheiro_dados")

    veredito = verify([*base, uma, outra])

    assert veredito.status == BIFURCADA
    assert veredito.forks == (3, 3)


def test_at12_hash_reprodutivel():
    linha = _cadeia(1)[0]
    reordenada = dict(reversed(list(linha.items())))

    assert row_hash(reordenada, linha["prev_hash"]) == linha["hash"]


def test_hash_ignora_microssegundos_e_fuso_de_origem():
    """O instante gravado pelo banco volta sem microssegundos; o hash não pode depender disso."""
    linha = _cadeia(1)[0]
    do_banco = {**linha, "at": linha["at"].replace(tzinfo=UTC)}

    assert row_hash(do_banco, linha["prev_hash"]) == linha["hash"]


def test_instante_sem_fuso_vindo_do_banco_e_utc():
    """Sem este cuidado, toda a trilha pareceria adulterada num servidor fora de UTC."""
    linha = _cadeia(1)[0]
    ingenuo = {**linha, "at": linha["at"].replace(tzinfo=None)}

    assert row_hash(ingenuo, linha["prev_hash"]) == linha["hash"]
    assert verify([ingenuo]).status == INTEGRA


def test_trilha_vazia_e_integra():
    assert verify([]).status == INTEGRA


def test_trilha_nasce_append_only_e_a_propriedade_e_reaplicada():
    from eict.config import Settings
    from eict.jobs.bootstrap_ops import ensure_tables

    class _Spark:
        def __init__(self):
            self.sql_emitido = []

        def sql(self, statement):
            self.sql_emitido.append(" ".join(statement.split()))

    spark = _Spark()
    ensure_tables(spark, Settings())

    criacao = next(item for item in spark.sql_emitido if "eict_ops.audit_log (" in item)
    assert "TBLPROPERTIES ('delta.appendOnly' = 'true')" in criacao
    assert any(item.startswith("ALTER TABLE") and "audit_log" in item for item in spark.sql_emitido)
