from __future__ import annotations

import pytest

from eict.domain.contracts import ColumnSpec, Contract, Rule
from eict.domain.rules import (
    EVALUATION_ERROR,
    PASSED,
    SAMPLE_LIMIT,
    VIOLATED,
    RuleCompilationError,
    compile_rule,
    evaluate,
    evaluate_freshness,
    evaluate_schema,
    evaluate_volume,
    missing_columns,
    parse_duration_seconds,
    type_mismatches,
    undeclared_columns,
    violation_limit,
)

ASSET = "workspace.eict_workload.orders"


def make_rule(dimension: str, expression: str = "", threshold: str = ">= 99.9%", **kwargs) -> Rule:
    return Rule(
        rule_id=f"{dimension}_rule",
        dimension=dimension,
        expression=expression,
        threshold=threshold,
        severity=kwargs.pop("severity", "critical"),
        owner="dados@example.com",
        **kwargs,
    )


def make_contract(rules: list[Rule], columns: list[ColumnSpec] | None = None) -> Contract:
    return Contract(
        contract_id="workspace.eict_workload.orders",
        version="1.0.0",
        status="active",
        owner="dados@example.com",
        producer="eict-demo-sales-daily",
        asset=ASSET,
        quality=rules,
        columns=columns or [],
    )


def compile_for(dimension: str, expression: str = "", **kwargs):
    rule = make_rule(dimension, expression, **kwargs)
    return rule, compile_rule(rule, make_contract([rule]))


def test_at003_completeness_gera_consulta_com_as_tres_colunas():
    _, compiled = compile_for("completeness", "customer_id")

    assert "count_if(customer_id IS NULL) AS numerator" in compiled.sql
    assert "count(*) AS denominator" in compiled.sql
    assert "AS sample" in compiled.sql
    assert ASSET in compiled.sql


def test_at004_uniqueness_conta_ocorrencias_duplicadas():
    _, compiled = compile_for("uniqueness", "order_id")

    assert "GROUP BY order_id" in compiled.sql
    assert "ocorrencias > 1" in compiled.sql


def test_at005_referential_gera_left_join():
    _, compiled = compile_for(
        "referential", "customer_id in workspace.eict_workload.customers.customer_id"
    )

    assert "LEFT JOIN workspace.eict_workload.customers pai" in compiled.sql
    assert "pai.customer_id IS NULL" in compiled.sql


def test_referential_com_expressao_invalida_falha_com_instrucao():
    with pytest.raises(RuleCompilationError, match="coluna in catalogo"):
        compile_for("referential", "customer_id")


def test_validity_nega_a_condicao_declarada():
    _, compiled = compile_for("validity", "amount > 0")

    assert "NOT (amount > 0)" in compiled.sql


def test_at006_freshness_usa_historico_do_delta():
    _, compiled = compile_for("freshness", threshold="<= 30m")

    assert "DESCRIBE HISTORY" in compiled.sql
    assert "atraso_s" in compiled.sql


def test_at007_volume_conta_linhas():
    _, compiled = compile_for("volume", threshold=">= 0.7")

    assert "count(*) AS numerator" in compiled.sql


def test_schema_nao_e_compilada_em_consulta():
    with pytest.raises(RuleCompilationError, match="catálogo"):
        compile_for("schema")


def test_regra_sem_expressao_obrigatoria_falha():
    with pytest.raises(RuleCompilationError, match="exige expression"):
        compile_for("completeness")


def test_amostra_e_limitada():
    _, compiled = compile_for("completeness", "customer_id")

    assert f", 1, {SAMPLE_LIMIT})" in compiled.sql


def test_at017_query_hash_e_estavel_e_depende_do_sql():
    _, primeira = compile_for("completeness", "customer_id")
    _, igual = compile_for("completeness", "customer_id")
    _, outra = compile_for("completeness", "order_id")

    assert primeira.query_hash == igual.query_hash
    assert primeira.query_hash != outra.query_hash


@pytest.mark.parametrize(
    ("threshold", "esperado"),
    [
        (">= 99.9%", 0.001),
        (">= 100%", 0.0),
        ("<= 0.1%", 0.001),
        (">= 0.95", 0.05),
    ],
)
def test_limite_declarado_vira_fracao_tolerada(threshold: str, esperado: float):
    assert violation_limit(threshold) == pytest.approx(esperado)


def test_limite_invalido_falha():
    with pytest.raises(RuleCompilationError, match="limite inválido"):
        violation_limit("quase tudo")


def test_at003_violacao_acima_do_limite():
    rule = make_rule("completeness", "customer_id", ">= 99.9%")

    assert evaluate(rule, numerator=4_812, denominator=60_000) == VIOLATED


def test_at009_dentro_do_limite_passa():
    rule = make_rule("completeness", "customer_id", ">= 99.9%")

    assert evaluate(rule, numerator=10, denominator=60_000) == PASSED


def test_tabela_vazia_nao_e_violacao():
    rule = make_rule("completeness", "customer_id")

    assert evaluate(rule, numerator=0, denominator=0) == PASSED


@pytest.mark.parametrize(
    ("duracao", "segundos"), [("30m", 1800), ("2h", 7200), ("1d", 86400), ("45s", 45)]
)
def test_duracao_do_slo(duracao: str, segundos: int):
    assert parse_duration_seconds(duracao) == segundos


def test_at008_coluna_do_contrato_ausente_e_detectada():
    esperado = [ColumnSpec(name="order_id", type="string"), ColumnSpec(name="amount", type="double")]
    atual = {"order_id": "string"}

    assert missing_columns(esperado, atual) == ["amount"]


def test_at008_tipo_divergente_e_detectado():
    esperado = [ColumnSpec(name="amount", type="double")]

    assert type_mismatches(esperado, {"amount": "string"}) == ["amount: contrato=double tabela=string"]


def test_tipos_equivalentes_nao_acusam_divergencia():
    esperado = [ColumnSpec(name="order_id", type="varchar(36)"), ColumnSpec(name="qtd", type="integer")]

    assert type_mismatches(esperado, {"order_id": "string", "qtd": "int"}) == []


def test_coluna_nova_e_apenas_informada():
    esperado = [ColumnSpec(name="order_id", type="string")]

    assert undeclared_columns(esperado, {"order_id": "string", "novo_campo": "string"}) == [
        "novo_campo"
    ]


def test_status_de_erro_e_distinto_de_violacao():
    assert EVALUATION_ERROR not in {PASSED, VIOLATED}


def test_at006_freshness_dentro_do_limite_passa():
    rule = make_rule("freshness", threshold="<= 30m")

    status, detalhe = evaluate_freshness(rule, delay_seconds=600)

    assert status == PASSED
    assert "600s" in detalhe


def test_at006_freshness_acima_do_limite_viola():
    rule = make_rule("freshness", threshold="<= 30m")

    status, detalhe = evaluate_freshness(rule, delay_seconds=5400)

    assert status == VIOLATED
    assert "acima do limite" in detalhe


def test_at007_volume_abaixo_da_mediana_viola():
    rule = make_rule("volume", threshold=">= 0.7")

    status, detalhe = evaluate_volume(rule, current=300, history=[1000, 1010, 990, 1005])

    assert status == VIOLATED
    assert "mediana" in detalhe


def test_volume_dentro_da_faixa_passa():
    rule = make_rule("volume", threshold=">= 0.7")

    status, _ = evaluate_volume(rule, current=950, history=[1000, 1010, 990, 1005])

    assert status == PASSED


def test_volume_sem_historico_suficiente_nao_acusa():
    rule = make_rule("volume", threshold=">= 0.7")

    status, detalhe = evaluate_volume(rule, current=10, history=[1000])

    assert status == PASSED
    assert "insuficiente" in detalhe


def test_at008_schema_com_coluna_ausente_viola():
    colunas = [ColumnSpec(name="order_id", type="string"), ColumnSpec(name="amount", type="double")]

    status, detalhe = evaluate_schema(colunas, {"order_id": "string"})

    assert status == VIOLATED
    assert "amount" in detalhe


def test_at008_schema_com_tipo_divergente_viola():
    colunas = [ColumnSpec(name="amount", type="double")]

    status, detalhe = evaluate_schema(colunas, {"amount": "string"})

    assert status == VIOLATED
    assert "tipos divergentes" in detalhe


def test_schema_com_coluna_nova_passa_informando():
    colunas = [ColumnSpec(name="order_id", type="string")]

    status, detalhe = evaluate_schema(colunas, {"order_id": "string", "canal": "string"})

    assert status == PASSED
    assert "canal" in detalhe
