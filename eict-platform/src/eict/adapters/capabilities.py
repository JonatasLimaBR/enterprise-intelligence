from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

BILLING_USAGE = "system.billing.usage"
BILLING_PRICES = "system.billing.list_prices"
TABLE_LINEAGE = "system.access.table_lineage"
QUERY_HISTORY = "system.query.history"

AVAILABLE = "available"
NOT_AVAILABLE = "not_available"


@dataclass(frozen=True)
class Capability:
    capability: str
    status: str
    detail: str
    checked_at: datetime

    @property
    def is_available(self) -> bool:
        return self.status == AVAILABLE


def probe_table(spark: Any, table: str) -> Capability:
    checked_at = datetime.now(UTC)
    try:
        spark.sql(f"SELECT 1 FROM {table} LIMIT 1").collect()
        return Capability(table, AVAILABLE, "select ok", checked_at)
    except Exception as exc:
        return Capability(table, NOT_AVAILABLE, str(exc)[:300], checked_at)


def probe_volume(spark: Any, path: str) -> Capability:
    checked_at = datetime.now(UTC)
    try:
        spark.sql(f"LIST '{path}'").collect()
        return Capability(f"volume:{path}", AVAILABLE, "list ok", checked_at)
    except Exception as exc:
        return Capability(f"volume:{path}", NOT_AVAILABLE, str(exc)[:300], checked_at)


def discover(spark: Any, landing_dir: str) -> list[Capability]:
    return [
        probe_table(spark, BILLING_USAGE),
        probe_table(spark, BILLING_PRICES),
        probe_table(spark, TABLE_LINEAGE),
        probe_table(spark, QUERY_HISTORY),
        probe_volume(spark, landing_dir),
    ]


def status_of(capabilities: list[Capability], capability: str) -> bool:
    for item in capabilities:
        if item.capability == capability:
            return item.is_available
    return False
