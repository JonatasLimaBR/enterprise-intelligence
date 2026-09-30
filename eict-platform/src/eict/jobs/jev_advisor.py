"""Estágio `jev_advisor`: recomendações do Jev nas zonas cinzentas (read-only).

Egress desligado por padrão: sem advisor habilitado em `jev/advisors.yaml` ou sem `jev_api_key`, não sai
nada. O Jev recomenda; a política determinística e o review humano autorizam. Grava em `ops.recommendations`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from eict.adapters import store
from eict.adapters.jev import JevClient, load_jev_config
from eict.config import Settings, parse_settings
from eict.domain.jev_advisor import (
    connector_calls,
    recommendation_row,
    runbook_calls,
    to_recommendation,
    triage_calls,
)

logger = logging.getLogger(__name__)

POLICY_VERSION = "jev-advisor-v1"
LOOKBACK_HOURS = 24


def _query(spark: Any, sql: str) -> list[dict]:
    try:
        return store.query(spark, sql)
    except Exception:
        return []


def load_recent_incidents(spark: Any, settings: Settings, now: datetime) -> list[dict]:
    floor = (now - timedelta(hours=LOOKBACK_HOURS)).astimezone(UTC).isoformat(sep=" ", timespec="seconds")
    return _query(
        spark,
        f"SELECT * FROM {settings.table('ops', 'incidents')} WHERE updated_at >= TIMESTAMP '{floor}'",
    )


def load_degraded_connectors(spark: Any, settings: Settings) -> list[dict]:
    return _query(
        spark,
        f"SELECT connector, status, detail FROM {settings.table('ops', 'connector_health')} "
        "WHERE status = 'degradado'",
    )


def load_tied_runbooks(spark: Any, settings: Settings) -> list[dict]:
    linhas = _query(
        spark,
        f"SELECT ir.incident_id AS incident_id, i.type AS incident_type, "
        f"collect_set(ir.runbook_id) AS candidate_ids "
        f"FROM {settings.table('ops', 'incident_runbooks')} ir "
        f"JOIN {settings.table('ops', 'incidents')} i ON ir.incident_id = i.incident_id "
        f"GROUP BY ir.incident_id, i.type HAVING size(collect_set(ir.runbook_id)) >= 2",
    )
    return [{**linha, "cause": ""} for linha in linhas]


def collect_calls(spark: Any, settings: Settings, enabled: frozenset[str], now: datetime) -> list:
    calls = []
    if "triage" in enabled:
        calls += triage_calls(load_recent_incidents(spark, settings, now))
    if "connector" in enabled:
        calls += connector_calls(load_degraded_connectors(spark, settings))
    if "runbook" in enabled:
        calls += runbook_calls(load_tied_runbooks(spark, settings))
    return calls


def main(argv: list[str] | None = None) -> None:
    settings = parse_settings(argv)
    config = load_jev_config(settings.jev_dir)
    if not config.enabled:
        logger.info("jev_advisor desligado (nenhum advisor habilitado)")
        return

    from databricks.sdk import WorkspaceClient

    try:
        token = WorkspaceClient().dbutils.secrets.get(settings.secret_scope, "jev_api_key")
    except Exception:
        token = ""
    if not token:
        logger.info("sem jev_api_key; jev_advisor não envia nada")
        return

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(UTC)
    client = JevClient(token=token)

    recs = []
    for call in collect_calls(spark, settings, config.enabled, now):
        rec = to_recommendation(call, client.decide(call.state, call.question), config.threshold, POLICY_VERSION)
        if rec is not None:
            recs.append(rec)

    if recs:
        linhas = [{**recommendation_row(rec), "created_at": now} for rec in recs]
        store.insert_missing(spark, settings.table("ops", "recommendations"), linhas, "recommendation_id")
    logger.info("jev_advisor: %s recomendação(ões)", len(recs))


if __name__ == "__main__":
    main()
