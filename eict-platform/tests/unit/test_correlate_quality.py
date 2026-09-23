"""O correlator de qualidade num ciclo que toca mais de um ativo.

Um ciclo real raramente tem uma violação só. Estes testes cobrem justamente o que
só aparece com vários ativos: cada evidência e cada hipótese precisa continuar
apontando para o incidente que a gerou.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from eict.domain.impact import Edge
from eict.jobs.correlate_quality import QualityInput, correlate_quality
from tests.unit.test_quality_incidents import ORDERS, SALES, TENANT, make_result

NOW = datetime(2026, 9, 22, 14, tzinfo=UTC)
CUSTOMERS = "workspace.eict_workload.customers"


def _payload(results) -> QualityInput:
    return QualityInput(results=results, contracts={}, changes=[], producer_states={})


def test_cada_hipotese_fica_no_incidente_que_a_gerou():
    resultados = [
        make_result("orders_unique", asset=ORDERS, dimension="uniqueness"),
        make_result("customers_schema", asset=CUSTOMERS, dimension="schema"),
    ]

    touched, _, _, hypotheses = correlate_quality(_payload(resultados), [], TENANT, NOW)

    por_assunto = {incident.subject: incident.incident_id for incident in touched}
    alvos = {incident_id for incident_id, _ in hypotheses}

    assert alvos == {por_assunto[ORDERS], por_assunto[CUSTOMERS]}


def test_cada_evidencia_fica_no_incidente_que_a_gerou():
    resultados = [
        make_result("orders_unique", asset=ORDERS, dimension="uniqueness"),
        make_result("sales_fresh", asset=SALES, dimension="freshness"),
    ]

    touched, _, evidences, _ = correlate_quality(_payload(resultados), [], TENANT, NOW)

    por_assunto = {incident.subject: incident.incident_id for incident in touched}
    assert {incident_id for incident_id, _ in evidences} == set(por_assunto.values())


def test_violacao_e_falha_de_engine_no_mesmo_ativo_sao_incidentes_distintos():
    resultados = [
        make_result("customers_schema", asset=CUSTOMERS, dimension="schema"),
        make_result("customers_region", asset=CUSTOMERS, status="evaluation_error"),
    ]

    touched, _, evidences, _ = correlate_quality(_payload(resultados), [], TENANT, NOW)

    tipos = {incident.type for incident in touched}
    assert tipos == {"contract_violation", "quality_engine_failure"}
    assert len({incident.incident_id for incident in touched}) == 2
    assert len({incident_id for incident_id, _ in evidences}) == 2


def test_um_ativo_so_continua_com_tudo_no_mesmo_incidente():
    resultados = [
        make_result("orders_unique", asset=ORDERS, dimension="uniqueness"),
        make_result("orders_amount", asset=ORDERS, dimension="completeness"),
    ]

    touched, _, evidences, hypotheses = correlate_quality(_payload(resultados), [], TENANT, NOW)

    assert len(touched) == 1
    unico = touched[0].incident_id
    assert {incident_id for incident_id, _ in evidences} == {unico}
    assert {incident_id for incident_id, _ in hypotheses} == {unico}


def test_engine_failure_ja_aberto_e_atualizado_nao_recriado():
    """O ativo com violação E falha de avaliação: o segundo incidente tem de sobreviver.

    O `result_id` muda a cada ciclo porque carrega o instante da avaliação. Se o
    incidente aberto não for encontrado, um novo nasce toda vez — e a promessa de
    um incidente por problema cai.
    """
    primeiro = correlate_quality(
        _payload([make_result("customers_region", asset=CUSTOMERS, status="evaluation_error")]),
        [],
        TENANT,
        NOW,
    )[0]
    aberto = [incident for incident in primeiro if incident.type == "quality_engine_failure"]

    ciclo_seguinte = [
        make_result("customers_schema", asset=CUSTOMERS, dimension="schema"),
        replace(
            make_result("customers_region", asset=CUSTOMERS, status="evaluation_error"),
            result_id="res-customers_region-ciclo-2",
        ),
    ]
    touched, _, _, _ = correlate_quality(_payload(ciclo_seguinte), aberto, TENANT, NOW)

    falhas = [incident for incident in touched if incident.type == "quality_engine_failure"]
    assert len(falhas) == 1
    assert falhas[0].incident_id == aberto[0].incident_id


def _com_grafo(results, graph, changed):
    return QualityInput(
        results=results,
        contracts={},
        changes=[],
        producer_states={},
        graph=graph,
        changed_upstream=changed,
    )


def _aresta(source: str, target: str, entity_type: str = "JOB", entity_id: str = "j1") -> Edge:
    return Edge(
        source=source,
        target=target,
        entity_type=entity_type,
        entity_id=entity_id,
        last_seen=NOW,
    )


def test_at11_mudanca_de_schema_a_montante_destrava_upstream_change():
    """A hipótese vivia em 0,05 porque `upstream_schema_changed` nunca era calculado."""
    bronze = "workspace.eict_workload.bronze"
    grafo = (_aresta(bronze, ORDERS),)
    payload = _com_grafo(
        [make_result("orders_schema", asset=ORDERS, dimension="schema")],
        grafo,
        frozenset({bronze}),
    )

    _, _, _, hypotheses = correlate_quality(payload, [], TENANT, NOW)
    upstream = next(h for _, h in hypotheses if h.code == "upstream_change")

    assert upstream.confidence > 0.05


def test_sem_mudanca_a_montante_a_hipotese_segue_contradita():
    bronze = "workspace.eict_workload.bronze"
    payload = _com_grafo(
        [make_result("orders_schema", asset=ORDERS, dimension="schema")],
        (_aresta(bronze, ORDERS),),
        frozenset(),
    )

    _, _, _, hypotheses = correlate_quality(payload, [], TENANT, NOW)
    upstream = next(h for _, h in hypotheses if h.code == "upstream_change")

    assert upstream.confidence == 0.05


def test_impacto_downstream_entra_no_incidente():
    dashboard_edge = Edge(
        source=ORDERS,
        target="",
        entity_type="DASHBOARD_V3",
        entity_id="painel",
        last_seen=NOW,
    )
    payload = _com_grafo(
        [make_result("orders_unique", asset=ORDERS, dimension="uniqueness", severity="warning")],
        (dashboard_edge,),
        frozenset(),
    )

    touched, _, _, _ = correlate_quality(payload, [], TENANT, NOW)
    incidente = touched[0]

    assert incidente.impact_score > 0
    assert incidente.severity == "critical"
    assert incidente.escalated_from == "warning"
    assert "consumo humano" in incidente.escalation_reason


def test_sem_grafo_nao_ha_impacto_nem_elevacao():
    payload = _com_grafo(
        [make_result("orders_unique", asset=ORDERS, severity="warning")], (), frozenset()
    )

    touched, _, _, _ = correlate_quality(payload, [], TENANT, NOW)

    assert touched[0].impact_score == 0.0
    assert touched[0].severity == "warning"
    assert touched[0].escalated_from == ""


def test_auto_resolucao_fecha_o_que_passou_e_preserva_o_que_viola():
    """Dois ativos avaliados, um ainda violando: só o outro fecha."""
    from eict.domain.incidents import CONTRACT_VIOLATION

    abertos = correlate_quality(
        _payload([make_result("r1", asset=ORDERS), make_result("r2", asset=SALES)]),
        [],
        TENANT,
        NOW,
    )[0]

    touched, entries, _, _ = correlate_quality(
        _payload(
            [
                replace(make_result("r1", asset=ORDERS, status="passed"), result_id="r1-b"),
                replace(make_result("r2", asset=SALES), result_id="r2-b"),
            ]
        ),
        abertos,
        TENANT,
        NOW,
    )

    fechados = [item for item in touched if item.state == "recovered"]
    assert [item.subject for item in fechados] == [ORDERS]
    assert any(entry.kind == "auto_resolved" for entry in entries)
    assert all(item.type == CONTRACT_VIOLATION for item in fechados)


def test_ativo_sem_avaliacao_corrente_nao_e_fechado():
    abertos = correlate_quality(
        _payload([make_result("r1", asset=ORDERS)]), [], TENANT, NOW
    )[0]

    touched, _, _, _ = correlate_quality(
        _payload([replace(make_result("r2", asset=SALES), result_id="r2-b")]),
        abertos,
        TENANT,
        NOW,
    )

    assert all(item.state != "recovered" for item in touched if item.subject == ORDERS)
