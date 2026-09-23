"""As arestas tipadas e a precedência entre o que se afirma e o que se descobre."""

from __future__ import annotations

from datetime import UTC, datetime

from eict.domain.impact import Edge
from eict.domain.ontology import (
    ASSERTED,
    CONSUMES,
    CONTAINS_SENSITIVE_DATA,
    DISCOVERED,
    IMPLEMENTS_METRIC,
    OWNED_BY,
    PRODUCES,
    SUPPORTED_PREDICATES,
    UNSUPPORTED_PREDICATES,
    from_contracts,
    from_lineage,
    from_metrics,
    merge,
)

NOW = datetime(2026, 9, 22, 18, tzinfo=UTC)
ORDERS = "workspace.eict_workload.orders"
SALES = "workspace.eict_workload.sales_daily"


class _Contrato:
    def __init__(self, asset=SALES, producer="job-sales", owner="dono@exemplo.com",
                 consumers=(), classification="internal"):
        self.asset = asset
        self.producer = producer
        self.owner = owner
        self.consumers = consumers
        self.classification = classification


class _Declaracao:
    def __init__(self, asset=SALES, metric_id="revenue", canonical=True):
        self.asset = asset
        self.metric_id = metric_id
        self.is_canonical = canonical


def _aresta(source=ORDERS, target=SALES):
    return Edge(source=source, target=target, entity_type="JOB", entity_id="j1", last_seen=NOW)


def test_at17_aresta_do_lineage_e_descoberta():
    arestas = from_lineage([_aresta()], NOW)

    produces = next(item for item in arestas if item.predicate == PRODUCES)

    assert produces.status == DISCOVERED
    assert produces.origin == "lineage"
    assert 0.8 <= produces.confidence < 1.0


def test_lineage_gera_a_relacao_e_a_inversa():
    arestas = from_lineage([_aresta()], NOW)

    assert {item.predicate for item in arestas} == {PRODUCES, CONSUMES}


def test_at18_aresta_de_contrato_e_afirmada():
    arestas = from_contracts([_Contrato()], NOW)

    dono = next(item for item in arestas if item.predicate == OWNED_BY)

    assert dono.status == ASSERTED
    assert dono.confidence == 1.0
    assert dono.object == "dono@exemplo.com"


def test_afirmada_prevalece_sobre_descoberta():
    descoberta = from_lineage([_aresta(source="job-sales", target=SALES)], NOW)
    afirmada = from_contracts([_Contrato()], NOW)

    unidas = merge(descoberta, afirmada)
    produces = [
        item
        for item in unidas
        if item.predicate == PRODUCES and item.subject == "job-sales" and item.object == SALES
    ]

    assert produces[0].status == ASSERTED


def test_a_descoberta_divergente_nao_e_apagada():
    """A divergência entre declarado e observado é informação, não ruído."""
    descoberta = from_lineage([_aresta(source="job-sales", target=SALES)], NOW)
    afirmada = from_contracts([_Contrato()], NOW)

    unidas = merge(descoberta, afirmada)
    produces = [
        item
        for item in unidas
        if item.predicate == PRODUCES and item.subject == "job-sales" and item.object == SALES
    ]

    assert len(produces) == 2
    assert {item.status for item in produces} == {ASSERTED, DISCOVERED}


def test_metrica_canonica_vira_implements_metric():
    arestas = from_metrics([_Declaracao()], NOW)

    assert arestas[0].predicate == IMPLEMENTS_METRIC
    assert arestas[0].status == ASSERTED


def test_metrica_proposta_nao_entra_na_ontologia():
    assert from_metrics([_Declaracao(canonical=False)], NOW) == []


def test_classificacao_interna_nao_marca_dado_sensivel():
    arestas = from_contracts([_Contrato(classification="internal")], NOW)

    assert CONTAINS_SENSITIVE_DATA not in {item.predicate for item in arestas}


def test_classificacao_restrita_marca_dado_sensivel():
    arestas = from_contracts([_Contrato(classification="restricted")], NOW)

    assert CONTAINS_SENSITIVE_DATA in {item.predicate for item in arestas}


def test_consumidor_declarado_vira_aresta_afirmada():
    arestas = from_contracts([_Contrato(consumers=("painel",))], NOW)

    consome = [item for item in arestas if item.predicate == CONSUMES]

    assert consome[0].subject == "painel"
    assert consome[0].status == ASSERTED


def test_edge_id_e_estavel_para_a_mesma_tripla():
    uma = from_contracts([_Contrato()], NOW)[0]
    outra = from_contracts([_Contrato()], NOW)[0]

    assert uma.edge_id == outra.edge_id


def test_as_relacoes_sem_fonte_nao_sao_suportadas():
    """Registrado no código, não só no documento."""
    assert UNSUPPORTED_PREDICATES.isdisjoint(SUPPORTED_PREDICATES)
    assert "supports_process" in UNSUPPORTED_PREDICATES


def test_merge_sem_entradas_devolve_vazio():
    assert merge([], []) == ()
