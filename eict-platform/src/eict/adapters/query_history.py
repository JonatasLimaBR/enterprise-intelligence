"""Horas em que cada warehouse teve consulta, de `system.query.history`.

Uma hora está ocupada se alguma consulta começou antes do fim dela e terminou depois do início.
Consulta sem `end_time` (ainda rodando) ocupa até agora.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from eict.adapters import capabilities as capability_probe
from eict.adapters import store


def busy_hours_sql(start: datetime, end: datetime) -> str:
    return f"""
    SELECT DISTINCT q.compute.warehouse_id AS warehouse_id, hora AS hour
    FROM {capability_probe.QUERY_HISTORY} q
    LATERAL VIEW EXPLODE(
        SEQUENCE(
            DATE_TRUNC('HOUR', q.start_time),
            DATE_TRUNC('HOUR', COALESCE(q.end_time, CURRENT_TIMESTAMP())),
            INTERVAL 1 HOUR
        )
    ) AS hora
    WHERE q.compute.warehouse_id IS NOT NULL
      AND q.start_time < TIMESTAMP '{end:%Y-%m-%d %H:%M:%S}'
      AND COALESCE(q.end_time, CURRENT_TIMESTAMP()) > TIMESTAMP '{start:%Y-%m-%d %H:%M:%S}'
    """


def busy_hours(spark: Any, start: datetime, end: datetime) -> frozenset[tuple[str, datetime]]:
    return frozenset(
        (str(row["warehouse_id"]), store.ensure_utc(row["hour"]))
        for row in store.query(spark, busy_hours_sql(start, end))
    )
