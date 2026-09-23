"""A travessia do grafo de lineage e a elevação de severidade que ela justifica."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from eict.domain.impact import (
    DOWNSTREAM,
    UPSTREAM,
    Edge,
    ImpactResult,
    edge_weight,
    escalation,
    recency_weight,
    traverse,
)

NOW = datetime(2026, 9, 22, 14, tzinfo=UTC)
ORDERS = "workspace.eict_workload.orders"
SALES = "workspace.eict_workload.sales_daily"
BACKUP = "workspace.eict_workload.orders_contract_backup"
DASHBOARD = "DASHBOARD_V3/painel-comercial"


def aresta(
    source: str,
    target: str = "",
    entity_type: str = "JOB",
    entity_id: str = "job-1",
    dias: int = 0,
) -> Edge:
    return Edge(
        source=source,
        target=target,
        entity_type=entity_type,
        entity_id=entity_id,
        last_seen=NOW - timedelta(days=dias),
    )


def test_at01_ciclo_no_grafo_nao_trava_a_travessia():
    """O grafo real tem `orders → orders_contract_backup → orders`."""
    arestas = (aresta(ORDERS, BACKUP), aresta(BACKUP, ORDERS))

    resultado = traverse(arestas, ORDERS, NOW, max_depth=5)

    assert [node.asset for node in resultado.nodes] == [BACKUP]


def test_at02_profundidade_limita_a_travessia():
    cadeia = tuple(aresta(f"t{i}", f"t{i + 1}") for i in range(10))

    resultado = traverse(cadeia, "t0", NOW, max_depth=3)

    assert {node.asset for node in resultado.nodes} == {"t1", "t2", "t3"}
    assert max(node.depth for node in resultado.nodes) == 3


def test_at03_aresta_sem_tipo_e_marcada_incerta_e_pesa_menos():
    incerta = aresta(ORDERS, SALES, entity_type="", entity_id="")
    confirmada = aresta(ORDERS, SALES)

    assert incerta.is_uncertain
    assert not confirmada.is_uncertain
    assert edge_weight(incerta, NOW) < edge_weight(confirmada, NOW)

    resultado = traverse((incerta,), ORDERS, NOW)

    assert resultado.uncertain_assets == (SALES,)


def test_at04_contribuicao_decai_com_a_distancia():
    arestas = (aresta("A", "B"), aresta("B", "C"))

    resultado = traverse(arestas, "A", NOW)
    por_ativo = {node.asset: node.score for node in resultado.nodes}

    assert por_ativo["B"] > por_ativo["C"]


def test_at05_raio_em_consumo_humano_eleva_ate_critical():
    arestas = (aresta(ORDERS, "", entity_type="DASHBOARD_V3", entity_id="painel-comercial"),)
    resultado = traverse(arestas, ORDERS, NOW)

    subida = escalation("warning", resultado)

    assert subida is not None
    assert subida.to_severity == "critical"
    assert subida.from_severity == "warning"


def test_at05b_nenhuma_elevacao_chega_a_blocking():
    arestas = (aresta(ORDERS, "", entity_type="DASHBOARD_V3", entity_id="painel"),)
    resultado = traverse(arestas, ORDERS, NOW)

    for partida in ("info", "warning", "high"):
        subida = escalation(partida, resultado)
        assert subida is not None
        assert subida.to_severity != "blocking"


def test_at06_incidente_ja_em_blocking_nao_e_tocado():
    arestas = (aresta(ORDERS, "", entity_type="DASHBOARD_V3", entity_id="painel"),)
    resultado = traverse(arestas, ORDERS, NOW)

    assert escalation("blocking", resultado) is None
    assert escalation("critical", resultado) is None


def test_at07_elevacao_grava_ativo_e_aresta():
    edge = aresta(ORDERS, "", entity_type="DASHBOARD_V3", entity_id="painel-comercial")
    resultado = traverse((edge,), ORDERS, NOW)

    subida = escalation("warning", resultado)

    assert subida.asset == DASHBOARD
    assert subida.edge_id == edge.edge_id
    assert "consumo humano" in subida.reason


def test_consumo_por_job_sozinho_nao_eleva():
    """Job downstream é impacto, mas não é consumo humano."""
    resultado = traverse((aresta(ORDERS, SALES),), ORDERS, NOW)

    assert resultado.nodes
    assert escalation("warning", resultado) is None


def test_at09_ruido_de_demo_fica_fora_do_raio():
    arestas = (aresta(ORDERS, BACKUP), aresta(ORDERS, SALES))

    resultado = traverse(arestas, ORDERS, NOW, excluded=("_contract_backup",))

    assert resultado.assets == (SALES,)


def test_at13_grafo_desconexo_devolve_vazio_sem_erro():
    resultado = traverse((aresta("X", "Y"),), ORDERS, NOW)

    assert resultado.nodes == ()
    assert resultado.score == 0.0


def test_sem_arestas_devolve_resultado_vazio():
    assert traverse((), ORDERS, NOW) == ImpactResult()
    assert traverse((), ORDERS, NOW).score == 0.0


def test_at14_grafo_de_500_arestas_termina_rapido():
    arestas = tuple(aresta(f"n{i}", f"n{i + 1}") for i in range(500))

    comeco = time.monotonic()
    resultado = traverse(arestas, "n0", NOW, max_depth=5)

    assert time.monotonic() - comeco < 1.0
    assert len(resultado.nodes) == 5


def test_at15_dois_saltos_confirmados_superam_um_salto_incerto():
    """O contraexemplo que derrubou a premissa do caminho mais curto.

    Um salto incerto vale 0,4 × 0,5 = 0,20. Dois saltos confirmados de dashboard
    valem 1,0 × 0,5 × 1,0 × 0,5 = 0,25. Parar na primeira visita perderia isso.
    """
    alvo = "alvo"
    atalho_incerto = aresta(ORDERS, alvo, entity_type="", entity_id="")
    ponte = aresta(ORDERS, "meio", entity_type="DASHBOARD_V3", entity_id="d1")
    longo = aresta("meio", alvo, entity_type="DASHBOARD_V3", entity_id="d2")

    resultado = traverse((atalho_incerto, ponte, longo), ORDERS, NOW, max_depth=3)
    node = next(item for item in resultado.nodes if item.asset == alvo)

    assert node.depth == 2
    assert node.score > 0.20


def test_cada_ativo_aparece_uma_vez_so():
    arestas = (aresta(ORDERS, SALES), aresta(ORDERS, SALES, entity_id="job-2"))

    resultado = traverse(arestas, ORDERS, NOW)

    assert len(resultado.assets) == len(set(resultado.assets))


def test_travessia_upstream_anda_no_sentido_contrario():
    arestas = (aresta("bronze", "silver"), aresta("silver", "gold"))

    resultado = traverse(arestas, "gold", NOW, direction=UPSTREAM, max_depth=3)

    assert set(resultado.assets) == {"silver", "bronze"}


def test_downstream_e_upstream_nao_se_misturam():
    arestas = (aresta("bronze", "silver"), aresta("silver", "gold"))

    frente = traverse(arestas, "silver", NOW, direction=DOWNSTREAM)
    tras = traverse(arestas, "silver", NOW, direction=UPSTREAM)

    assert frente.assets == ("gold",)
    assert tras.assets == ("bronze",)


def test_aresta_recente_conta_inteira_e_velha_conta_menos():
    nova = aresta(ORDERS, SALES, dias=1)
    velha = aresta(ORDERS, SALES, dias=120)

    assert recency_weight(nova, NOW) == 1.0
    assert recency_weight(velha, NOW) == 0.3
    assert recency_weight(aresta(ORDERS, SALES, dias=45), NOW) < 1.0


def test_aresta_do_futuro_nao_ganha_peso_extra():
    """Relógio adiantado no workspace não deve virar bônus."""
    assert recency_weight(aresta(ORDERS, SALES, dias=-5), NOW) == 1.0


def test_entidade_sem_tabela_alvo_vira_no_pelo_tipo_e_id():
    edge = aresta(ORDERS, "", entity_type="DASHBOARD_V3", entity_id="painel-comercial")

    assert edge.node == DASHBOARD


def test_profundidade_zero_nao_percorre_nada():
    assert traverse((aresta(ORDERS, SALES),), ORDERS, NOW, max_depth=0).nodes == ()


def test_aresta_sem_alvo_e_sem_entidade_nao_vira_no():
    """O lineage emite linhas assim; elas criavam um nó `desconhecido/` no raio."""
    anonima = Edge(source=ORDERS, target="", entity_type="", entity_id="", last_seen=NOW)

    assert anonima.is_anonymous
    assert traverse((anonima,), ORDERS, NOW).nodes == ()


def test_aresta_sem_alvo_mas_com_entidade_continua_valendo():
    identificada = Edge(
        source=ORDERS, target="", entity_type="", entity_id="job-77", last_seen=NOW
    )

    assert not identificada.is_anonymous
    assert traverse((identificada,), ORDERS, NOW).assets == ("desconhecido/job-77",)
