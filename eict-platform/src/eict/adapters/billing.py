"""Consultas de showback sobre `system.billing`: uso por recurso e run, e o total do período.

Duas consultas de propósito: a primeira alimenta a alocação; a segunda soma o mesmo escopo sem
agrupar, e a reconciliação compara as duas. O preço é o de lista **vigente no instante do uso**.

Os campos de `usage_metadata` variam com a versão do schema; os ausentes viram `NULL` em vez de
derrubar a consulta — o custo cai em "recurso não identificado", visível.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from eict.adapters import capabilities as capability_probe
from eict.adapters import store

METADATA_FIELDS = ("job_id", "job_name", "job_run_id", "dlt_pipeline_id", "warehouse_id", "app_id", "app_name")


@dataclass(frozen=True)
class PeriodTotal:
    total_cost: Decimal
    unpriced_dbus: Decimal
    currencies: tuple[str, ...]
    watermark: datetime | None


def to_decimal(value: Any) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal("0")


def metadata_fields(spark: Any) -> frozenset[str]:
    schema = spark.table(capability_probe.BILLING_USAGE).schema
    return frozenset(schema["usage_metadata"].dataType.fieldNames())


def _field(name: str, available: frozenset[str]) -> str:
    if name in available:
        return f"CAST(u.usage_metadata.{name} AS STRING) AS {name}"
    return f"CAST(NULL AS STRING) AS {name}"


def _scope(start: datetime, end: datetime, workspace_id: str) -> str:
    filtro = (
        f"u.usage_start_time >= TIMESTAMP '{start:%Y-%m-%d %H:%M:%S}' "
        f"AND u.usage_start_time < TIMESTAMP '{end:%Y-%m-%d %H:%M:%S}'"
    )
    if workspace_id:
        filtro += f" AND u.workspace_id = '{workspace_id}'"
    return filtro


PRICE_JOIN = f"""
    LEFT JOIN {capability_probe.BILLING_PRICES} p
      ON u.sku_name = p.sku_name
     AND u.cloud = p.cloud
     AND u.usage_unit = p.usage_unit
     AND u.usage_start_time >= p.price_start_time
     AND (p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time)
"""


def usage_sql(start: datetime, end: datetime, workspace_id: str, available: frozenset[str]) -> str:
    colunas = ",\n           ".join(_field(nome, available) for nome in METADATA_FIELDS)
    return f"""
    SELECT {colunas},
           u.billing_origin_product AS origin_product,
           SUM(u.usage_quantity) AS dbus,
           SUM(u.usage_quantity * p.pricing.default) AS cost
    FROM {capability_probe.BILLING_USAGE} u
    {PRICE_JOIN}
    WHERE {_scope(start, end, workspace_id)}
    GROUP BY ALL
    """


def total_sql(start: datetime, end: datetime, workspace_id: str) -> str:
    return f"""
    SELECT SUM(u.usage_quantity * p.pricing.default) AS total_cost,
           SUM(CASE WHEN p.sku_name IS NULL THEN u.usage_quantity END) AS unpriced_dbus,
           COLLECT_SET(p.currency_code) AS currencies,
           MAX(u.usage_end_time) AS watermark
    FROM {capability_probe.BILLING_USAGE} u
    {PRICE_JOIN}
    WHERE {_scope(start, end, workspace_id)}
    """


def usage_records(spark: Any, start: datetime, end: datetime, workspace_id: str) -> list[dict]:
    return store.query(spark, usage_sql(start, end, workspace_id, metadata_fields(spark)))


def period_total(spark: Any, start: datetime, end: datetime, workspace_id: str) -> PeriodTotal:
    linhas = store.query(spark, total_sql(start, end, workspace_id))
    linha = linhas[0] if linhas else {}
    return PeriodTotal(
        total_cost=to_decimal(linha.get("total_cost")),
        unpriced_dbus=to_decimal(linha.get("unpriced_dbus")),
        currencies=tuple(sorted(linha.get("currencies") or ())),
        watermark=linha.get("watermark"),
    )


def _ids(values: list[str]) -> str:
    """Só ids numéricos entram no SQL: vêm do billing e do SDK, mas a regra não depende disso."""
    return ", ".join(f"'{value}'" for value in sorted(set(values)) if value.isdigit())


def job_daily_sql(job_ids: list[str], start: datetime, end: datetime, workspace_id: str) -> str:
    return f"""
    SELECT CAST(u.usage_metadata.job_id AS STRING) AS job_id,
           CAST(u.usage_start_time AS DATE) AS day,
           SUM(u.usage_quantity * p.pricing.default) AS cost,
           COUNT(DISTINCT u.usage_metadata.job_run_id) AS runs
    FROM {capability_probe.BILLING_USAGE} u
    {PRICE_JOIN}
    WHERE {_scope(start, end, workspace_id)}
      AND u.usage_metadata.job_id IN ({_ids(job_ids)})
    GROUP BY ALL
    """


def warehouse_hours_sql(start: datetime, end: datetime, workspace_id: str) -> str:
    return f"""
    SELECT CAST(u.usage_metadata.warehouse_id AS STRING) AS warehouse_id,
           DATE_TRUNC('HOUR', u.usage_start_time) AS hour,
           SUM(u.usage_quantity * p.pricing.default) AS cost
    FROM {capability_probe.BILLING_USAGE} u
    {PRICE_JOIN}
    WHERE {_scope(start, end, workspace_id)}
      AND u.usage_metadata.warehouse_id IS NOT NULL
    GROUP BY ALL
    """


def job_daily_costs(spark: Any, job_ids: list[str], start: datetime, end: datetime, workspace_id: str) -> list[dict]:
    if not _ids(job_ids):
        return []
    return store.query(spark, job_daily_sql(job_ids, start, end, workspace_id))


def warehouse_hours(spark: Any, start: datetime, end: datetime, workspace_id: str) -> list[dict]:
    return store.query(spark, warehouse_hours_sql(start, end, workspace_id))
