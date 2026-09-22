from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from eict.domain.incidents import CONTRACT_VIOLATION, open_or_update_for_asset
from eict.domain.models import RuleResult
from eict.domain.quality_incidents import (
    build_error_evidence,
    build_evidence,
    first_result_id,
    group_errors,
    group_violations,
    has_blocking,
    incident_severity,
    violation_summary,
)

NOW = datetime(2026, 9, 21, 12, tzinfo=UTC)
ORDERS = "workspace.eict_workload.orders"
SALES = "workspace.eict_workload.sales_daily"
TENANT = "demo"


def make_result(
    rule_id: str,
    status: str = "violated",
    asset: str = ORDERS,
    severity: str = "critical",
    dimension: str = "completeness",
    numerator: int = 4_812,
    denominator: int = 60_000,
    minutes: int = 0,
    **kwargs,
) -> RuleResult:
    return RuleResult(
        result_id=f"res-{rule_id}",
        contract_id=asset,
        rule_id=rule_id,
        asset=asset,
        dimension=dimension,
        status=status,
        threshold=">= 99.9%",
        severity=severity,
        window="current_state",
        query_hash="abc123",
        evaluated_at=NOW + timedelta(minutes=minutes),
        numerator=numerator,
        denominator=denominator,
        **kwargs,
    )


def test_at011_regras_do_mesmo_ativo_viram_um_grupo():
    resultados = [
        make_result("orders_customer_id_not_null"),
        make_result("orders_order_id_unique", dimension="uniqueness"),
        make_result("orders_customer_exists", dimension="referential"),
        make_result("orders_amount_positive", status="passed"),
    ]

    grupos = group_violations(resultados)

    assert list(grupos) == [ORDERS]
    assert len(grupos[ORDERS]) == 3


def test_at012_ativos_diferentes_viram_grupos_distintos():
    resultados = [
        make_result("orders_customer_id_not_null"),
        make_result("sales_daily_fresh", asset=SALES, dimension="freshness"),
    ]

    grupos = group_violations(resultados)

    assert sorted(grupos) == sorted([ORDERS, SALES])


def test_regras_que_passam_nao_geram_grupo():
    assert group_violations([make_result("ok", status="passed")]) == {}


def test_at010_erro_de_execucao_nao_entra_como_violacao():
    resultados = [
        make_result("com_erro", status="evaluation_error", error_message="tabela não existe"),
        make_result("ok", status="passed"),
    ]

    assert group_violations(resultados) == {}
    assert list(group_errors(resultados)) == [ORDERS]


def test_severidade_do_incidente_e_a_mais_alta():
    resultados = [
        make_result("a", severity="warning"),
        make_result("b", severity="blocking"),
        make_result("c", severity="critical"),
    ]

    assert incident_severity(resultados) == "blocking"


def test_severidade_padrao_sem_resultados():
    assert incident_severity([]) == "warning"


def test_primeiro_resultado_define_a_identidade_do_incidente():
    resultados = [
        make_result("segunda", minutes=5),
        make_result("primeira", minutes=0),
    ]

    assert first_result_id(resultados) == "res-primeira"


def test_at005_evidencia_carrega_consulta_resultado_e_amostra():
    resultado = make_result(
        "orders_customer_id_not_null",
        sample=('{"order_id":"O-1"}', '{"order_id":"O-2"}'),
    )

    evidencia = build_evidence(resultado, NOW)
    payload = json.loads(evidencia.value)

    assert evidencia.kind == "rule_violation"
    assert "4812 de 60000" in evidencia.summary
    assert payload["query_hash"] == "abc123"
    assert payload["threshold"] == ">= 99.9%"
    assert len(payload["sample"]) == 2


def test_evidencia_de_erro_carrega_a_mensagem():
    resultado = make_result(
        "quebrada", status="evaluation_error", error_message="TABLE_OR_VIEW_NOT_FOUND"
    )

    evidencia = build_error_evidence(resultado, NOW)

    assert evidencia.kind == "rule_evaluation_error"
    assert "não foi possível avaliar" in evidencia.summary
    assert evidencia.value == "TABLE_OR_VIEW_NOT_FOUND"


def test_at007_gate_bloqueante_e_sinalizado():
    assert has_blocking([make_result("schema", severity="blocking")]) is True
    assert has_blocking([make_result("outra", severity="critical")]) is False


def test_resumo_lista_dimensoes_e_bloqueantes():
    resultados = [
        make_result("a", dimension="completeness"),
        make_result("b", dimension="schema", severity="blocking"),
    ]

    texto = violation_summary(ORDERS, resultados)

    assert "2 regra(s)" in texto
    assert "completeness, schema" in texto
    assert "1 bloqueante" in texto


def test_at011_incidente_de_qualidade_agrupa_por_ativo():
    incidente, criado = open_or_update_for_asset(
        [], TENANT, ORDERS, CONTRACT_VIOLATION, "res-1", NOW
    )
    atualizado, recriado = open_or_update_for_asset(
        [incidente], TENANT, ORDERS, CONTRACT_VIOLATION, "res-2", NOW + timedelta(minutes=5)
    )

    assert criado is True
    assert recriado is False
    assert atualizado.correlation_key == incidente.correlation_key
    assert atualizado.last_run_id == "res-2"
    assert atualizado.subject == ORDERS


def test_at012_ativos_diferentes_geram_incidentes_distintos():
    do_orders, _ = open_or_update_for_asset([], TENANT, ORDERS, CONTRACT_VIOLATION, "res-1", NOW)
    do_sales, criado = open_or_update_for_asset(
        [do_orders], TENANT, SALES, CONTRACT_VIOLATION, "res-2", NOW
    )

    assert criado is True
    assert do_sales.correlation_key != do_orders.correlation_key


def test_at016_consumidores_declarados_e_descobertos_ficam_separados():
    incidente, _ = open_or_update_for_asset([], TENANT, SALES, CONTRACT_VIOLATION, "res-1", NOW)

    com_listas = incidente.with_declared_consumers(("painel_comercial", "time_financeiro")).with_assets(
        ("painel_comercial", "api_previsao")
    )

    assert com_listas.undeclared_consumers == ("api_previsao",)
    assert com_listas.unseen_declared_consumers == ("time_financeiro",)
