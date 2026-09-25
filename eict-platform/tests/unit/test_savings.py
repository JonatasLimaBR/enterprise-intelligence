"""Detectores, estimativa, grupos, risco e medição da economia (AT-01…10, AT-15…19, SC1–SC7).

Os valores vêm da demo: custo incremental de US$ 0,0682 por run e 60M linhas de entrada.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from eict.domain.impact import Edge
from eict.domain.savings import (
    ALTO,
    AMOSTRA_INSUFICIENTE,
    BAIXO,
    DESCARTADA,
    EFEITO_COLATERAL,
    EM_INICIATIVA,
    EM_MEDICAO,
    EXPIRADA,
    FALHA,
    IMPLEMENTADA,
    MEDIO,
    NAO_AVALIADO,
    NAO_REALIZADA,
    OCIOSO,
    POR_DIA,
    POR_MILHAO,
    REALIZADA,
    REGRESSAO,
    SCHEDULE,
    JobSchedule,
    Policy,
    RunRecord,
    SavingsConfigError,
    WarehouseHour,
    assign_groups,
    detect_failed,
    detect_idle_warehouse,
    detect_regression,
    detect_schedule,
    is_non_prod,
    link_initiatives,
    measure,
    parse_policy,
    projected,
    risk,
)

AGORA = datetime(2026, 9, 25, 12, tzinfo=UTC)
POL = Policy()
INCREMENTAL = Decimal("0.0682")


def _incidente(i="inc-1", tipo="runtime_regression", state="detected", job="j1"):
    return {"incident_id": i, "type": tipo, "state": state, "subject": job, "job_id": job}


def _custos(n, incidente="inc-1", valor=0.0682, prefixo="r"):
    return [
        {"run_id": f"{prefixo}{k}", "incident_id": incidente, "status": "available", "incremental_cost_usd": valor}
        for k in range(n)
    ]


def _regressao(n_runs_incidente=5, runs_30d=20, dias=30, causas=None, falhados=frozenset(), limiar="0.10"):
    return detect_regression(
        [_incidente()], _custos(n_runs_incidente), causas or {"inc-1": ("skew_join_change", 0.9)},
        {"j1": runs_30d}, {"j1": dias}, {"j1": "sales-daily"}, falhados,
        Policy(threshold_usd_month=Decimal(limiar)),
    )


def test_at01_regressao_estima_incremental_vezes_runs_do_mes_com_confianca_da_hipotese():
    [op] = _regressao().opportunities
    assert op.source == REGRESSAO
    assert op.estimate.value == INCREMENTAL * 20
    assert op.estimate.low == op.estimate.high == op.estimate.value
    assert (op.confidence, op.hypothesis_code) == (0.9, "skew_join_change")
    assert op.formula and op.recommendation and op.subject_name == "sales-daily"


def test_at02_menos_de_cinco_runs_vira_faixa():
    detector = detect_regression(
        [_incidente()],
        [{"run_id": "a", "incident_id": "inc-1", "status": "available", "incremental_cost_usd": 0.05},
         {"run_id": "b", "incident_id": "inc-1", "status": "available", "incremental_cost_usd": 0.09},
         {"run_id": "c", "incident_id": "inc-1", "status": "available", "incremental_cost_usd": 0.07}],
        {}, {"j1": 20}, {"j1": 30}, {}, frozenset(), POL,
    )
    [op] = detector.opportunities
    assert op.estimate.n == 3
    assert (op.estimate.low, op.estimate.value, op.estimate.high) == (
        Decimal("1.00"), Decimal("1.40"), Decimal("1.80"))


def test_historico_curto_projeta_e_marca():
    [op] = _regressao(runs_30d=10, dias=10).opportunities
    assert op.estimate.short_history
    assert op.estimate.value == INCREMENTAL * 10 * 3


def test_regressao_fechada_ou_pending_nao_gera():
    fechado = detect_regression([_incidente(state="recovered")], _custos(5), {}, {"j1": 20}, {"j1": 30}, {},
                                frozenset(), POL)
    pendente = detect_regression([_incidente()], [{**linha, "status": "pending"} for linha in _custos(5)], {},
                                 {"j1": 20}, {"j1": 30}, {}, frozenset(), POL)
    assert fechado.opportunities == () and fechado.evaluated == 0
    assert pendente.opportunities == ()


def test_at09_sc3_abaixo_do_limiar_e_contado_nunca_some():
    detector = _regressao(runs_30d=1, n_runs_incidente=1, limiar="0.10")
    assert detector.opportunities == ()
    assert detector.below_threshold == 1
    assert detector.below_threshold_usd == INCREMENTAL


def _run(i, job="j1", ok=True, custo="0.5", dias_atras=1, linhas=None):
    return RunRecord(f"{job}-r{i}", job, AGORA - timedelta(days=dias_atras), ok,
                     Decimal(custo) if custo is not None else None, linhas)


def test_at03_execucao_falhada_soma_custo_medido_com_confianca_alta():
    runs = [_run(i, ok=False) for i in range(4)] + [_run(9, ok=True)]
    [op] = detect_failed(runs, {"j1": 30}, {}, AGORA, POL).opportunities
    assert op.source == FALHA
    assert op.estimate.value == Decimal("2.0")
    assert op.confidence_label == "alta"
    assert len(op.evidence) == 4


def test_falha_fora_da_janela_nao_conta():
    runs = [_run(1, ok=False, dias_atras=40)]
    assert detect_failed(runs, {"j1": 30}, {}, AGORA, POL).opportunities == ()


def test_at06_schedule_nao_prod_ativo_gera_custo_mensal():
    detector = detect_schedule([JobSchedule("7", "eict-demo-sales-daily-dev", paused=False)],
                               {"7": (Decimal("3.20"), 30)}, {"7": 30}, AGORA, POL)
    [op] = detector.opportunities
    assert (op.source, op.estimate.value, op.confidence_label) == (SCHEDULE, Decimal("3.20"), "alta")


def test_at07_schedule_pausado_ou_prod_nao_gera():
    schedules = [JobSchedule("7", "x-dev", paused=True), JobSchedule("8", "x-prod", paused=False)]
    detector = detect_schedule(schedules, {"7": (Decimal("9"), 9), "8": (Decimal("9"), 9)}, {}, AGORA, POL)
    assert detector.opportunities == ()


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [("[dev fulano] eict-cycle-dev", True), ("x-staging", True), ("x-prod", False), ("devtools", False)],
)
def test_convencao_de_target_nao_prod(nome, esperado):
    assert is_non_prod(nome, POL.non_prod_targets) is esperado


def _hora(h, custo="1"):
    return WarehouseHour("wh", AGORA.replace(minute=0) - timedelta(hours=h), Decimal(custo))


def test_at04_warehouse_ocioso_custa_as_horas_sem_consulta():
    horas = [_hora(h) for h in range(10)]
    ocupadas = frozenset(("wh", horas[h].hour) for h in range(4))
    [op] = detect_idle_warehouse(horas, ocupadas, AGORA, POL).opportunities
    assert op.source == OCIOSO
    assert op.estimate.value == Decimal("6")
    assert op.evidence == ("6 de 10 horas faturadas sem consulta",)


def test_at05_sem_query_history_e_nao_avaliado():
    detector = detect_idle_warehouse([_hora(1)], None, AGORA, POL)
    assert detector.status == NAO_AVALIADO
    assert detector.opportunities == ()
    assert "query.history" in detector.reason


def test_at10_sc4_run_falhado_nao_conta_tambem_na_regressao():
    falhados = frozenset({"r0", "r1"})
    [op] = _regressao(falhados=falhados).opportunities
    assert "r0" not in op.evidence and op.estimate.n == 3


def test_schedule_contem_as_demais_do_mesmo_job():
    schedule = detect_schedule([JobSchedule("j1", "sales-daily-dev", False)], {"j1": (Decimal("5"), 10)},
                               {"j1": 30}, AGORA, POL).opportunities[0]
    regressao = _regressao().opportunities[0]
    agrupadas = {item.source: item for item in assign_groups([regressao, schedule], AGORA)}
    assert agrupadas[SCHEDULE].counted and not agrupadas[REGRESSAO].counted
    assert agrupadas[REGRESSAO].contained_in == schedule.opportunity_id
    assert agrupadas[REGRESSAO].group_id == agrupadas[SCHEDULE].group_id


def test_falha_e_regressao_do_mesmo_job_contam_as_duas():
    falha = detect_failed([_run(1, ok=False)], {"j1": 30}, {}, AGORA, POL).opportunities[0]
    regressao = _regressao(falhados=frozenset({"j1-r1"})).opportunities[0]
    assert all(item.counted for item in assign_groups([falha, regressao], AGORA))


def _aresta(origem, destino="", tipo="", entidade=""):
    return Edge(origem, destino, tipo, entidade, AGORA)


PRODUTOS = {"sales-daily": ("w.sales",)}


def test_at08_consumo_humano_por_arestas_confirmadas_e_risco_alto():
    arestas = (_aresta("w.sales", tipo="DASHBOARD_V3", entidade="painel"),)
    nivel, motivo = risk("[dev x] sales-daily-dev", PRODUTOS, arestas, AGORA)
    assert nivel == ALTO and "SLO" in motivo


def test_consumo_humano_so_por_aresta_incerta_e_medio():
    arestas = (_aresta("w.sales", "w.meio"), _aresta("w.meio", tipo="DASHBOARD", entidade="painel"))
    nivel, motivo = risk("sales-daily", PRODUTOS, arestas, AGORA)
    assert nivel == MEDIO and "incerta" in motivo


def test_sem_ativo_mapeado_e_medio_nunca_baixo():
    assert risk("outro-job", PRODUTOS, (), AGORA)[0] == MEDIO


def test_ativos_sem_consumidor_humano_e_baixo():
    assert risk("sales-daily", PRODUTOS, (_aresta("w.sales", "w.x", "TABLE", "t"),), AGORA)[0] == BAIXO


def test_iniciativa_ativa_marca_em_iniciativa_e_tira_do_kpi():
    [op] = _regressao().opportunities
    iniciativas = [{"initiative_id": "ini-1", "opportunity_id": "outra", "source": REGRESSAO, "subject": "j1",
                    "state": IMPLEMENTADA}]
    [ligada] = link_initiatives([op], iniciativas, {"ini-1": EM_MEDICAO})
    assert (ligada.status, ligada.initiative_id, ligada.counted) == (EM_INICIATIVA, "ini-1", False)


def test_iniciativa_encerrada_libera_nova_oportunidade_e_descartada_some():
    [op] = _regressao().opportunities
    encerrada = [{"initiative_id": "ini-1", "opportunity_id": "x", "source": REGRESSAO, "subject": "j1",
                  "state": IMPLEMENTADA}]
    assert link_initiatives([op], encerrada, {"ini-1": REALIZADA})[0].counted
    descartada = [{"initiative_id": "ini-2", "opportunity_id": op.opportunity_id, "source": REGRESSAO,
                   "subject": "j1", "state": DESCARTADA}]
    assert link_initiatives([op], descartada, {}) == []


def _iniciativa(fonte=REGRESSAO, dias_atras=20, custo=None):
    return {"initiative_id": "ini-1", "source": fonte, "state": IMPLEMENTADA,
            "implemented_at": AGORA - timedelta(days=dias_atras), "implementation_cost_usd": custo}


def _runs_medicao(antes, depois, linhas_antes=60_000_000, linhas_depois=60_000_000, dias_atras=20):
    ancora = AGORA - timedelta(days=dias_atras)
    runs = [RunRecord(f"a{i}", "j1", ancora - timedelta(days=i + 1), True, Decimal(c), linhas_antes)
            for i, c in enumerate(antes)]
    runs += [RunRecord(f"d{i}", "j1", ancora + timedelta(days=i), True, Decimal(c), linhas_depois)
             for i, c in enumerate(depois)]
    return runs


def test_at15_realizada_por_milhao_de_linhas():
    runs = _runs_medicao(["18"] * 8, ["12"] * 6)
    resultado = measure(_iniciativa(), runs, {}, [], AGORA, POL)
    assert resultado.state == REALIZADA
    assert resultado.unit == POR_MILHAO
    assert (resultado.baseline_median, resultado.after_median) == (Decimal("0.3"), Decimal("0.2"))
    assert resultado.gross_usd > 0 and resultado.net_usd is None
    assert "líquida não calculada" in resultado.reason


def test_sc6_volume_dobra_e_custo_por_unidade_cai_conta_como_realizada():
    runs = _runs_medicao(["18"] * 8, ["24"] * 6, linhas_depois=120_000_000)
    assert measure(_iniciativa(), runs, {}, [], AGORA, POL).state == REALIZADA


def test_em_medicao_antes_de_fechar_a_janela():
    assert measure(_iniciativa(dias_atras=5), [], {}, [], AGORA, POL).state == EM_MEDICAO


def test_at16_amostra_insuficiente_e_depois_expirada():
    runs = _runs_medicao(["18"] * 8, ["12"] * 3)
    assert measure(_iniciativa(), runs, {}, [], AGORA, POL).state == AMOSTRA_INSUFICIENTE
    runs_velhos = _runs_medicao(["18"] * 8, ["12"] * 3, dias_atras=61)
    assert measure(_iniciativa(dias_atras=61), runs_velhos, {}, [], AGORA, POL).state == EXPIRADA


def test_amostra_insuficiente_estende_a_janela_depois_ate_ter_o_minimo():
    ancora = AGORA - timedelta(days=30)
    runs = [RunRecord(f"a{i}", "j1", ancora - timedelta(days=i + 1), True, Decimal("18"), 60_000_000)
            for i in range(6)]
    runs += [RunRecord(f"d{i}", "j1", ancora + timedelta(days=3 * i), True, Decimal("12"), 60_000_000)
             for i in range(6)]
    assert measure(_iniciativa(dias_atras=30), runs, {}, [], AGORA, POL).state == REALIZADA


def test_at17_mais_caro_por_unidade_nao_realizada():
    runs = _runs_medicao(["12"] * 6, ["18"] * 6)
    assert measure(_iniciativa(), runs, {}, [], AGORA, POL).state == NAO_REALIZADA


def test_at18_efeito_colateral_fica_fora_do_kpi():
    runs = _runs_medicao(["18"] * 8, ["12"] * 6)
    incidente = {"incident_id": "inc-q", "type": "contract_violation",
                 "detected_at": AGORA - timedelta(days=15)}
    resultado = measure(_iniciativa(), runs, {}, [incidente], AGORA, POL)
    assert resultado.state == EFEITO_COLATERAL
    assert resultado.side_effect_incidents == ("inc-q",)


def test_at19_custo_de_implementacao_maior_que_a_bruta():
    runs = _runs_medicao(["18"] * 8, ["12"] * 6)
    assert measure(_iniciativa(custo=1_000_000), runs, {}, [], AGORA, POL).state == NAO_REALIZADA


def test_schedule_mede_custo_por_dia():
    ancora = AGORA - timedelta(days=20)
    diarios = {(ancora - timedelta(days=i + 1)).date(): Decimal("2") for i in range(14)}
    diarios |= {(ancora + timedelta(days=i)).date(): Decimal("0.5") for i in range(14)}
    resultado = measure(_iniciativa(fonte=SCHEDULE), [], diarios, [], AGORA, POL)
    assert (resultado.state, resultado.unit) == (REALIZADA, POR_DIA)
    assert resultado.gross_usd == Decimal("1.5") * 30


def test_execucao_falhada_mede_custo_total_por_run_bem_sucedido():
    ancora = AGORA - timedelta(days=20)
    antes = [RunRecord(f"a{i}", "j1", ancora - timedelta(days=i + 1), i % 2 == 0, Decimal("1")) for i in range(10)]
    depois = [RunRecord(f"d{i}", "j1", ancora + timedelta(days=i), True, Decimal("1")) for i in range(6)]
    resultado = measure(_iniciativa(fonte=FALHA), antes + depois, {}, [], AGORA, POL)
    assert (resultado.baseline_median, resultado.after_median) == (Decimal("2"), Decimal("1"))
    assert resultado.state == REALIZADA


def test_politica_invalida_e_recusada():
    with pytest.raises(SavingsConfigError):
        parse_policy({"min_runs": 0})
    with pytest.raises(SavingsConfigError):
        parse_policy({"threshold_usd_month": "abc"})
    assert parse_policy({"threshold_usd_month": "50"}).threshold_usd_month == Decimal("50")


def test_projected_sem_runs_devolve_none():
    assert projected([], 10, 30, POL) is None
