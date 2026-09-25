"""Forma das consultas de showback: preço vigente, escopo e campos ausentes (D5, D6, D9)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from eict.adapters import billing

INICIO = datetime(2026, 9, 1, tzinfo=UTC)
FIM = datetime(2026, 9, 25, 12, tzinfo=UTC)
TODOS = frozenset(billing.METADATA_FIELDS)


def test_preco_vigente_no_instante_do_uso():
    sql = billing.usage_sql(INICIO, FIM, "", TODOS)
    assert "u.usage_start_time >= p.price_start_time" in sql
    assert "p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time" in sql
    assert "LEFT JOIN" in sql


def test_periodo_e_escopo_de_workspace():
    sql = billing.total_sql(INICIO, FIM, "42")
    assert "TIMESTAMP '2026-09-01 00:00:00'" in sql
    assert "TIMESTAMP '2026-09-25 12:00:00'" in sql
    assert "u.workspace_id = '42'" in sql


def test_sem_workspace_o_escopo_e_a_conta():
    assert "workspace_id" not in billing.total_sql(INICIO, FIM, "")


def test_campo_ausente_vira_null_em_vez_de_quebrar_a_consulta():
    sql = billing.usage_sql(INICIO, FIM, "", frozenset({"job_id", "job_run_id"}))
    assert "CAST(u.usage_metadata.job_id AS STRING) AS job_id" in sql
    assert "CAST(NULL AS STRING) AS app_id" in sql
    assert "usage_metadata.app_id" not in sql


def test_total_conta_dbus_sem_preco_e_watermark():
    sql = billing.total_sql(INICIO, FIM, "")
    assert "p.sku_name IS NULL" in sql
    assert "MAX(u.usage_end_time) AS watermark" in sql


def test_to_decimal_nao_herda_erro_de_float():
    assert billing.to_decimal(0.1) + billing.to_decimal(0.2) == Decimal("0.3")
    assert billing.to_decimal(None) == Decimal("0")
