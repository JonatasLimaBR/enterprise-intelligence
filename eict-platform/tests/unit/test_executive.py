"""Resumo executivo (SPEC-017 DASH-01): cada número com janela, fonte, amostra e confiança."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eict.domain.executive import ALTA, BAIXA, SEM_DADOS, rows, summarize

AGORA = datetime(2026, 9, 24, 22, tzinfo=UTC)


def _inc(i, state="detected", severity="high", tipo="runtime_regression", horas=2.0, **extra):
    return {
        "incident_id": f"inc-{i}",
        "subject": f"workspace.eict_workload.ativo{i}",
        "type": tipo,
        "state": state,
        "severity": severity,
        "detected_at": AGORA - timedelta(hours=horas + 1),
        "updated_at": AGORA - timedelta(hours=1),
        "last_run_id": f"run-{i}",
        **extra,
    }


def _metricas(incidents, costs=None, health=None):
    return {item.metric_id: item for item in summarize(incidents, costs or {}, health or [], AGORA)}


def test_ativos_contam_so_estados_ativos():
    m = _metricas([_inc(1), _inc(2, state="recovered"), _inc(3, tipo="sla_risk")])

    assert m["active_incidents"].value == 2
    assert "runtime_regression: 1" in m["active_incidents"].detail


def test_criticos():
    m = _metricas([_inc(1, severity="critical"), _inc(2, severity="warning"), _inc(3, severity="blocking")])

    assert m["critical_incidents"].value == 2


def test_mttr_usa_so_recuperados_e_mostra_a_amostra():
    recuperados = [_inc(i, state="recovered", horas=h) for i, h in enumerate([1.0, 2.0, 3.0])]
    fechado = _inc(9, state="closed", horas=50.0)

    m = _metricas([*recuperados, fechado])

    assert m["mttr_hours"].value == 2.0
    assert m["mttr_hours"].n == 3
    assert m["mttr_hours"].confidence == BAIXA
    assert m["administrative_closures"].value == 1


def test_mttr_com_amostra_grande_tem_confianca_alta():
    m = _metricas([_inc(i, state="recovered", horas=1.0) for i in range(6)])

    assert m["mttr_hours"].confidence == ALTA


def test_mttr_fora_da_janela_nao_conta():
    velho = _inc(1, state="recovered")
    velho["updated_at"] = AGORA - timedelta(days=10)

    m = _metricas([velho])

    assert m["mttr_hours"].value is None
    assert m["mttr_hours"].confidence == SEM_DADOS


def test_mtta_sem_reconhecimento_nunca_e_zero():
    m = _metricas([_inc(1)])

    assert m["mtta_hours"].value is None
    assert m["mtta_hours"].confidence == SEM_DADOS
    assert "1 ativo(s) sem reconhecimento" in m["mtta_hours"].detail


def test_mtta_mediana_dos_reconhecidos_e_pendentes_a_parte():
    reconhecidos = [
        _inc(i, acknowledged_at=AGORA - timedelta(hours=3) + timedelta(minutes=m))
        for i, m in enumerate([15, 30, 45])
    ]
    m = _metricas([*reconhecidos, _inc(9)])

    assert m["mtta_hours"].value == 0.5
    assert m["mtta_hours"].n == 3
    assert "1 ativo(s) sem reconhecimento" in m["mtta_hours"].detail


def test_sla_em_risco():
    m = _metricas([_inc(1, tipo="sla_risk"), _inc(2)])

    assert m["sla_at_risk"].value == 1
    assert "ativo1" in m["sla_at_risk"].detail


def test_impacto_une_ativos_e_ordena_pelo_score():
    a = _inc(1, impact_score=0.85, affected_assets=["painel", "x"])
    b = _inc(2, impact_score=1.675, affected_assets=["painel", "y", "z"])

    m = _metricas([a, b])

    assert m["impacted_assets"].value == 4
    assert m["impacted_assets"].detail.startswith("ativo2 (1.68")


def test_custo_soma_so_o_confirmado_e_conta_pendentes():
    custos = {
        "run-1": {"status": "available", "incremental_cost_usd": 0.0682},
        "run-2": {"status": "pending", "incremental_cost_usd": None},
    }

    m = _metricas([_inc(1), _inc(2)], custos)

    assert m["incremental_cost_usd"].value == 0.0682
    assert m["incremental_cost_usd"].n == 1
    assert "1 pendente" in m["incremental_cost_usd"].detail


def test_sem_custo_confirmado_e_nao_medido_nao_zero():
    m = _metricas([_inc(1)], {"run-1": {"status": "pending"}})

    assert m["incremental_cost_usd"].value is None


def test_conectores():
    saude = [{"connector": "github", "status": "degradado"}, {"connector": "databricks_jobs", "status": "saudavel"}]

    m = _metricas([], health=saude)

    assert m["unhealthy_connectors"].value == 1
    assert m["unhealthy_connectors"].confidence == ALTA


def test_conectores_sem_avaliacao():
    assert _metricas([])["unhealthy_connectors"].confidence == SEM_DADOS


def test_toda_metrica_tem_janela_fonte_formula_e_confianca():
    for item in summarize([_inc(1)], {}, [], AGORA):
        assert item.window and item.source and item.formula and item.confidence, item.metric_id


def test_linhas_para_o_read_model():
    linhas = rows(summarize([_inc(1)], {}, [], AGORA), AGORA)

    assert len(linhas) == 10
    assert all(linha["computed_at"] == AGORA and linha["policy_version"] for linha in linhas)


def test_taxa_de_recomendacoes_aceitas():
    m = {
        item.metric_id: item
        for item in summarize([], {}, [], AGORA, [{"decision": "accepted"}, {"decision": "rejected"}])
    }

    assert m["recommendations_accepted"].value == 50.0
    assert m["recommendations_accepted"].n == 2
