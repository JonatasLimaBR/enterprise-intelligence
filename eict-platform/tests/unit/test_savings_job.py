"""Etapa de economia: read models, fonte indisponível, iniciativa ativa, congelamento e falha (AT-05, SC7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from eict.adapters import billing, query_history, savings_config
from eict.config import Settings
from eict.domain import executive
from eict.domain import savings as sv
from eict.domain.impact import Edge
from eict.jobs import savings

AGORA = datetime(2026, 9, 25, 12, tzinfo=UTC)


def _inputs(**extra):
    base = dict(
        policy=sv.Policy(),
        config_error="",
        incidents=[{"incident_id": "inc-1", "type": "runtime_regression", "state": "detected", "subject": "1",
                    "job_id": "1"}],
        run_costs=[{"run_id": f"r{i}", "incident_id": "inc-1", "status": "available", "incremental_cost_usd": 0.0682}
                   for i in range(5)],
        causes={"inc-1": ("skew_join_change", 0.9)},
        runs=[sv.RunRecord(f"x{i}", "1", AGORA - timedelta(days=i + 1), True, Decimal("0.3"), 60_000_000)
              for i in range(20)],
        first_seen={"1": AGORA - timedelta(days=60)},
        job_names={"1": "eict-demo-sales-daily-dev"},
        schedules=[],
        job_daily={},
        warehouse_hours=[],
        busy=None,
        owners={"1": ("comercial-dados@exemplo.com", True)},
        producer_assets={"eict-demo-sales-daily": ("w.sales",)},
        edges=(Edge("w.sales", "", "DASHBOARD_V3", "painel", AGORA),),
        platform_warehouse_id="wh",
        initiatives=[],
    )
    return savings.SavingsInputs(**{**base, **extra})


def test_build_rows_gera_a_oportunidade_da_demo_com_dono_e_risco():
    linhas = savings.build_rows(_inputs(), AGORA)
    [op] = linhas["savings_opportunities"]
    assert op["source"] == sv.REGRESSAO
    assert op["estimate_usd"] == Decimal("1.3640")
    assert (op["owner"], op["risk"], op["counted"]) == ("comercial-dados@exemplo.com", sv.ALTO, True)
    assert op["currency"] == "USD" and op["price_basis"] == "lista" and op["period_label"] == "2026-09"


def test_at05_detectores_nao_avaliados_aparecem_com_motivo():
    detectores = {row["source"]: row for row in savings.build_rows(_inputs(schedules=None), AGORA)["savings_detectors"]}
    assert detectores[sv.OCIOSO]["status"] == sv.NAO_AVALIADO
    assert detectores[sv.SCHEDULE]["status"] == sv.NAO_AVALIADO
    assert detectores[sv.REGRESSAO]["status"] == sv.AVALIADO
    assert set(detectores) == set(sv.SOURCES)


def test_billing_indisponivel_deixa_falhas_nao_avaliadas():
    detectores = {row["source"]: row for row in savings.build_rows(_inputs(billing_available=False), AGORA)[
        "savings_detectors"]}
    assert detectores[sv.FALHA]["status"] == sv.NAO_AVALIADO


def _iniciativa(**extra):
    return {"initiative_id": "ini-1", "opportunity_id": "antiga", "source": sv.REGRESSAO, "subject": "1",
            "job_id": "1", "state": sv.APROVADA, "estimate_usd": Decimal("9.99"), **extra}


def test_iniciativa_aprovada_tira_a_oportunidade_do_kpi():
    [op] = savings.build_rows(_inputs(initiatives=[_iniciativa()]), AGORA)["savings_opportunities"]
    assert (op["status"], op["initiative_id"], op["counted"]) == (sv.EM_INICIATIVA, "ini-1", False)


def test_sc7_iniciativa_sobrevive_ao_sumico_da_oportunidade_e_e_medida():
    implementada = _iniciativa(state=sv.IMPLEMENTADA, implemented_at=AGORA - timedelta(days=5))
    linhas = savings.build_rows(_inputs(incidents=[], initiatives=[implementada]), AGORA)
    assert linhas["savings_opportunities"] == []
    [medida] = linhas["savings_realization"]
    assert (medida["initiative_id"], medida["state"]) == ("ini-1", sv.EM_MEDICAO)


def test_warehouse_ocioso_sem_query_history_nao_e_medido():
    iniciativa = _iniciativa(source=sv.OCIOSO, subject="wh", job_id="", state=sv.IMPLEMENTADA,
                             implemented_at=AGORA - timedelta(days=20))
    [medida] = savings.build_rows(_inputs(initiatives=[iniciativa]), AGORA)["savings_realization"]
    assert medida["state"] == sv.AMOSTRA_INSUFICIENTE
    assert "query.history" in medida["reason"]


def test_warehouse_da_plataforma_tem_risco_medio_com_motivo():
    horas = [sv.WarehouseHour("wh", AGORA.replace(minute=0) - timedelta(hours=h), Decimal("1")) for h in range(5)]
    linhas = savings.build_rows(_inputs(incidents=[], warehouse_hours=horas, busy=frozenset()), AGORA)
    [op] = linhas["savings_opportunities"]
    assert (op["source"], op["risk"]) == (sv.OCIOSO, sv.MEDIO)
    assert "console" in op["risk_reason"]


def test_job_nao_alocado_pede_dono():
    [op] = savings.build_rows(_inputs(owners={"1": ("", False)}), AGORA)["savings_opportunities"]
    assert op["note"] == "atribuir dono primeiro"


def test_top_causes_ignora_hipotese_descartada():
    hipoteses = {"inc-1": [
        {"code": "a", "rank": 1, "confidence": 0.9, "status": "rejected"},
        {"code": "b", "rank": 2, "confidence": 0.4, "status": "active"},
    ]}
    assert savings.top_causes(hipoteses) == {"inc-1": ("b", 0.4)}


def test_job_costs_window_e_dias_observados():
    diario = {"7": {(AGORA - timedelta(days=d)).date(): (Decimal("1"), 2) for d in range(5)}}
    custos, dias = savings.job_costs_window(diario, AGORA, 30)
    assert custos["7"] == (Decimal("5"), 10)
    assert dias["7"] == 5


def test_recente_nao_recalcula(monkeypatch):
    monkeypatch.setattr(savings, "last_computed", lambda spark, settings: AGORA - timedelta(minutes=5))
    monkeypatch.setattr(savings, "load_inputs", _explode)
    assert savings.refresh(object(), Settings(), AGORA) == {}


def _explode(*args, **kwargs):
    raise RuntimeError("billing indisponível")


def test_falha_na_leitura_nao_grava_nada(monkeypatch):
    escritas = []
    monkeypatch.setattr(savings, "last_computed", lambda spark, settings: None)
    monkeypatch.setattr(savings, "load_inputs", _explode)
    monkeypatch.setattr(savings.store, "replace_rows", lambda *args: escritas.append(args))
    with pytest.raises(RuntimeError):
        savings.refresh(object(), Settings(), AGORA)
    assert escritas == []


def test_politica_do_repositorio_carrega_sem_erro():
    politica, erro = savings_config.load(savings.policy_path(Settings()))
    assert erro == ""
    assert politica.threshold_usd_month == Decimal("0.10")


def test_politica_invalida_usa_defaults_e_informa(tmp_path):
    arquivo = tmp_path / "savings.yaml"
    arquivo.write_text("min_runs: 0\n", encoding="utf-8")
    politica, erro = savings_config.load(arquivo)
    assert politica == sv.Policy()
    assert "savings.yaml" in erro


def test_sql_de_query_history_e_billing_por_job():
    sql = query_history.busy_hours_sql(AGORA - timedelta(days=30), AGORA)
    assert "system.query.history" in sql and "INTERVAL 1 HOUR" in sql
    diario = billing.job_daily_sql(["123", "abc; DROP"], AGORA - timedelta(days=30), AGORA, "")
    assert "'123'" in diario and "DROP" not in diario


def test_kpis_de_economia_no_resumo_executivo():
    oportunidades = [{"status": "identificada", "counted": True, "estimate_usd": Decimal("1.36")},
                     {"status": "identificada", "counted": False, "estimate_usd": Decimal("5")},
                     {"status": "em_iniciativa", "counted": False, "estimate_usd": Decimal("7")}]
    iniciativas = [{"approved_at": AGORA - timedelta(days=1), "estimate_usd": Decimal("2")}]
    medidas = [{"state": "realizada", "net_usd": None, "gross_usd": Decimal("3")},
               {"state": "nao_realizada", "net_usd": Decimal("-1"), "gross_usd": Decimal("1")},
               {"state": "em_medicao"}]
    metricas = {item.metric_id: item for item in executive.summarize([], {}, [], AGORA, (),
                                                                      (oportunidades, iniciativas, medidas))}
    assert metricas["savings_identified_usd"].value == pytest.approx(1.36)
    assert metricas["savings_approved_usd"].value == pytest.approx(2)
    assert metricas["savings_realized_usd"].value == pytest.approx(3)
    assert metricas["savings_realization_rate"].value == pytest.approx(50)
