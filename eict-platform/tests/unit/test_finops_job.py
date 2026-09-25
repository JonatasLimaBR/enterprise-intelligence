"""Job de showback: cadência, períodos, watermark e nenhuma escrita em falha (AT-16, SC7)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from eict.adapters import billing
from eict.config import Settings
from eict.domain.allocation import APP, JOB, PIPELINE, WAREHOUSE, PlatformPool, build_rules, parse_domain, periods
from eict.jobs import finops

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))

from money import fmt_money, fmt_share  # noqa: E402

AGORA = datetime(2026, 9, 25, 12, tzinfo=UTC)
WATERMARK = datetime(2026, 9, 25, 7, tzinfo=UTC)
REGRAS = build_rules(
    [parse_domain({"business_unit": "v", "domain": "com", "owner": "d@x",
                   "products": [{"product": "p", "jobs": ["sales"]}]}, "com.yaml")],
    PlatformPool("plataforma-eict", "plat@x", ("eict-cycle",), (), "_platform.yaml"),
)


def _registro(job_id=None, run=None, custo="1", **extra):
    return {"job_id": job_id, "job_name": None, "job_run_id": run, "dlt_pipeline_id": None, "warehouse_id": None,
            "app_id": None, "app_name": None, "origin_product": "JOBS", "dbus": Decimal("1"), "cost": Decimal(custo),
            **extra}


def _entradas(total_corrente="6", moedas=("USD",)):
    anterior, corrente = periods(AGORA)
    return [
        finops.PeriodInput(anterior, [_registro("1", "r0", "2")],
                           billing.PeriodTotal(Decimal("2"), Decimal("0"), moedas, None)),
        finops.PeriodInput(
            corrente,
            [_registro("1", "r1", "1"), _registro("1", "r2", "3"), _registro("9", "c1", "2")],
            billing.PeriodTotal(Decimal(total_corrente), Decimal("0.5"), moedas, WATERMARK),
        ),
    ]


def _build(entradas=None):
    return finops.build_rows(
        entradas or _entradas(), REGRAS, [], {"1": "sales", "9": "eict-cycle-dev"},
        {"r1": True, "r2": True}, {"r1": 1_000_000, "r2": None}, [], [],
        frozenset({"eict-cycle"}), "workspace 42", AGORA,
    )


def test_at16_dois_periodos_e_watermark_so_no_corrente():
    reconciliacao = {row["period_label"]: row for row in _build()["cost_reconciliation"]}
    assert set(reconciliacao) == {"2026-08", "2026-09"}
    assert reconciliacao["2026-09"]["watermark"] == WATERMARK
    assert reconciliacao["2026-08"]["watermark"] is None
    assert "fechado" in reconciliacao["2026-08"]["period_status"]


def test_reconciliacao_por_periodo_com_categorias():
    corrente = next(row for row in _build()["cost_reconciliation"] if row["period_label"] == "2026-09")
    assert (corrente["allocated"], corrente["platform_pool"], corrente["unallocated"]) == (
        Decimal("4.0000"), Decimal("2.0000"), Decimal("0.0000"))
    assert corrente["reconciled"] is True
    assert corrente["unpriced_dbus"] == 0.5
    assert corrente["scope"] == "workspace 42"


def test_diferenca_contra_o_total_independente_marca_nao_reconciliado():
    corrente = next(row for row in _build(_entradas("600"))["cost_reconciliation"] if row["period_label"] == "2026-09")
    assert corrente["reconciled"] is False


def test_g8_toda_linha_tem_periodo_moeda_e_base_de_preco():
    for tabela in ("cost_allocation", "cost_reconciliation", "cost_units"):
        for row in _build()[tabela]:
            assert row["period_label"] and row["currency"] == "USD" and row["price_basis"] == "lista"


def test_unidades_por_run_e_por_ciclo():
    unidades = [row for row in _build()["cost_units"] if row["period_label"] == "2026-09"]
    por_run_sales = next(row for row in unidades if row["unit"] == "custo_por_run" and row["subject"] == "sales")
    assert (por_run_sales["median"], por_run_sales["n"], por_run_sales["owner"]) == (Decimal("2.0000"), 2, "d@x")
    ciclo = next(row for row in unidades if row["unit"] == "custo_por_ciclo_eict")
    assert ciclo["owner"] == "plat@x"
    assert ciclo["status"] == "sucesso_nao_verificado"
    assert any(row["unit"] == "custo_por_incidente" for row in unidades)


def test_to_lines_identifica_cada_tipo_de_recurso():
    linhas = finops.to_lines(
        [
            _registro("1", "r1", job_name="nome-do-billing"),
            _registro(dlt_pipeline_id="p1"),
            _registro(warehouse_id="w1"),
            _registro(app_name="eict-console-dev"),
            _registro(),
        ],
        {"1": "nome-monitorado"},
    )
    assert [linha.resource_kind for linha in linhas] == [JOB, PIPELINE, WAREHOUSE, APP, ""]
    assert linhas[0].resource_name == "nome-monitorado"


def test_nome_do_billing_quando_o_job_nao_e_monitorado():
    [linha] = finops.to_lines([_registro("5", "r", job_name="eict-cycle-dev")], {})
    assert linha.resource_name == "eict-cycle-dev"


def test_cadencia_de_uma_hora():
    assert finops.is_recent(AGORA - timedelta(minutes=59), AGORA)
    assert not finops.is_recent(AGORA - timedelta(minutes=61), AGORA)
    assert not finops.is_recent(None, AGORA)


def test_recente_nao_consulta_o_billing(monkeypatch):
    monkeypatch.setattr(finops, "last_computed", lambda spark, settings: AGORA - timedelta(minutes=10))
    monkeypatch.setattr(finops.billing, "usage_records", _explode)
    assert finops.refresh(object(), Settings(), AGORA) == {}


def _explode(*args, **kwargs):
    raise RuntimeError("billing indisponível")


def test_falha_no_billing_nao_grava_nada(monkeypatch):
    escritas = []
    monkeypatch.setattr(finops, "last_computed", lambda spark, settings: None)
    monkeypatch.setattr(finops, "workspace_scope", lambda: ("", "conta"))
    monkeypatch.setattr(finops.billing, "usage_records", _explode)
    monkeypatch.setattr(finops.store, "replace_rows", lambda *args: escritas.append(args))
    with pytest.raises(RuntimeError):
        finops.refresh(object(), Settings(), AGORA)
    assert escritas == []


def test_fmt_money_sempre_com_periodo_moeda_e_base():
    assert fmt_money(Decimal("1234.5"), "USD", "2026-09") == "US$ 1,234.5000 · 2026-09 · preço de lista"
    assert fmt_money(None, "USD", "2026-09") == "não medido · 2026-09"
    assert fmt_share(0.756) == "75.6%"
    assert fmt_share(None) == "sem base"
