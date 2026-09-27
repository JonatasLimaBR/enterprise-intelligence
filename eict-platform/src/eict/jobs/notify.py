"""Estágio `notify`: enfileira e envia as notificações de WhatsApp do ciclo.

Autocontido — não toca em `correlate` nem em `dispatch`. Decide os eventos materiais (domínio puro),
enfileira idempotentemente no `notification_outbox` e envia as vencidas pela Cloud API, com backoff e
DLQ. Config ausente/opt-out ⇒ não faz nada (fail-safe). Cada linha de update carrega o schema inteiro:
o MERGE é `UPDATE SET *` e omitir uma coluna a zeraria.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from eict.adapters import store
from eict.adapters.notification_config import load_config
from eict.adapters.whatsapp import (
    WhatsAppClient,
    WhatsAppPermanentError,
    WhatsAppRetryableError,
)
from eict.config import Settings, parse_settings
from eict.domain.notifications import NotificationConfig, NotificationMessage, messages_for

logger = logging.getLogger(__name__)

CHANNEL = "whatsapp"
MAX_ATTEMPTS = 5
BACKOFF_MINUTES = (1, 2, 4, 8, 16)
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
RETENTION_DAYS = 90
MAX_EVIDENCE = 2


@dataclass(frozen=True)
class OutboxEntry:
    dedup_key: str
    incident_id: str
    event: str
    severity: str
    destination: str
    template_name: str
    variables: tuple[str, ...]
    attempts: int
    created_at: Any


def _sql_ts(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(sep=" ", timespec="seconds")


def load_recent_incidents(spark: Any, settings: Settings, now: datetime, lookback_hours: int) -> list:
    floor = now - timedelta(hours=lookback_hours)
    records = store.query(
        spark,
        f"SELECT * FROM {settings.table('ops', 'incidents')} "
        f"WHERE updated_at >= TIMESTAMP '{_sql_ts(floor)}'",
    )
    return [store.to_incident(record) for record in records]


def load_evidence(spark: Any, settings: Settings, incident_ids: list[str]) -> dict[str, tuple[str, ...]]:
    if not incident_ids:
        return {}
    quoted = ", ".join(f"'{item}'" for item in incident_ids)
    rows = store.query(
        spark,
        f"SELECT incident_id, summary, observed_at FROM {settings.table('ops', 'evidence')} "
        f"WHERE incident_id IN ({quoted}) ORDER BY observed_at DESC",
    )
    grouped: dict[str, list[str]] = {}
    for row in rows:
        bucket = grouped.setdefault(row["incident_id"], [])
        if row.get("summary") and len(bucket) < MAX_EVIDENCE:
            bucket.append(row["summary"])
    return {key: tuple(value) for key, value in grouped.items()}


def enqueue_row(message: NotificationMessage, cfg: NotificationConfig, now: datetime) -> dict:
    return {
        "dedup_key": message.dedup_key,
        "incident_id": message.incident_id,
        "event": message.event,
        "severity": message.severity,
        "channel": CHANNEL,
        "destination": cfg.destination,
        "status": STATUS_PENDING,
        "attempts": 0,
        "next_attempt_at": message.send_after,
        "last_error": None,
        "message_id": None,
        "template_name": cfg.template_name,
        "variables_json": json.dumps(list(message.variables), ensure_ascii=False),
        "created_at": now,
        "updated_at": now,
    }


def due_entries(spark: Any, settings: Settings, now: datetime) -> list[OutboxEntry]:
    records = store.query(
        spark,
        f"""
        SELECT * FROM {settings.table('ops', 'notification_outbox')}
        WHERE status = '{STATUS_PENDING}'
          AND (next_attempt_at IS NULL OR next_attempt_at <= TIMESTAMP '{_sql_ts(now)}')
        """,
    )
    return [
        OutboxEntry(
            dedup_key=record["dedup_key"],
            incident_id=record.get("incident_id") or "",
            event=record.get("event") or "",
            severity=record.get("severity") or "",
            destination=record.get("destination") or "",
            template_name=record.get("template_name") or "",
            variables=tuple(json.loads(record["variables_json"]) if record.get("variables_json") else ()),
            attempts=int(record.get("attempts") or 0),
            created_at=record.get("created_at"),
        )
        for record in records
    ]


def next_backoff(attempts: int) -> timedelta:
    index = min(attempts, len(BACKOFF_MINUTES) - 1)
    return timedelta(minutes=BACKOFF_MINUTES[index])


def _row(entry: OutboxEntry, now: datetime, **overrides: Any) -> dict:
    base = {
        "dedup_key": entry.dedup_key,
        "incident_id": entry.incident_id,
        "event": entry.event,
        "severity": entry.severity,
        "channel": CHANNEL,
        "destination": entry.destination,
        "status": STATUS_PENDING,
        "attempts": entry.attempts + 1,
        "next_attempt_at": None,
        "last_error": None,
        "message_id": None,
        "template_name": entry.template_name,
        "variables_json": json.dumps(list(entry.variables), ensure_ascii=False),
        "created_at": entry.created_at,
        "updated_at": now,
    }
    base.update(overrides)
    return base


def _sent_row(entry: OutboxEntry, now: datetime, message_id: str) -> dict:
    return _row(entry, now, status=STATUS_SENT, message_id=message_id)


def _retry_row(entry: OutboxEntry, now: datetime, error: str) -> dict:
    attempts = entry.attempts + 1
    exhausted = attempts >= MAX_ATTEMPTS
    return _row(
        entry,
        now,
        status=STATUS_FAILED if exhausted else STATUS_PENDING,
        next_attempt_at=None if exhausted else now + next_backoff(attempts),
        last_error=error,
    )


def _failed_row(entry: OutboxEntry, now: datetime, error: str) -> dict:
    return _row(entry, now, status=STATUS_FAILED, last_error=error)


def dispatch_message(client: WhatsAppClient, entry: OutboxEntry, cfg: NotificationConfig, now: datetime) -> dict:
    try:
        message = client.send_template(entry.destination, entry.template_name, cfg.template_lang, entry.variables)
    except WhatsAppRetryableError as exc:
        return _retry_row(entry, now, str(exc)[:500])
    except WhatsAppPermanentError as exc:
        return _failed_row(entry, now, str(exc)[:500])
    return _sent_row(entry, now, message.message_id)


def link_incident(spark: Any, settings: Settings, row: dict) -> None:
    if row["status"] != STATUS_SENT or not row.get("message_id"):
        return
    spark.sql(
        f"""
        UPDATE {settings.table('ops', 'incidents')}
        SET notification_refs = array_distinct(
                array_union(coalesce(notification_refs, array()), array('{row["message_id"]}'))
            ),
            version = version + 1
        WHERE incident_id = '{row["incident_id"]}'
        """
    )


def record_dlq(spark: Any, settings: Settings, row: dict, now: datetime) -> None:
    if row["status"] != STATUS_FAILED:
        return
    store.append_rows(
        spark,
        settings.table("ops", "dlq"),
        [
            {
                "dlq_id": f"{CHANNEL}-{row['dedup_key']}-{row['attempts']}",
                "source": CHANNEL,
                "payload": row["variables_json"],
                "error": row["last_error"],
                "at": now,
            }
        ],
    )


def purge_expired(spark: Any, settings: Settings, now: datetime) -> None:
    floor = now - timedelta(days=RETENTION_DAYS)
    spark.sql(
        f"DELETE FROM {settings.table('ops', 'notification_outbox')} "
        f"WHERE updated_at < TIMESTAMP '{_sql_ts(floor)}'"
    )


def main(argv: list[str] | None = None) -> None:
    settings = parse_settings(argv)
    cfg = load_config(settings.notifications_dir)
    if cfg is None or not cfg.usable:
        logger.info("whatsapp não configurado ou opt-out; notify ignorado")
        return

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(UTC)

    incidents = load_recent_incidents(spark, settings, now, cfg.lookback_hours)
    evidence = load_evidence(spark, settings, [incident.incident_id for incident in incidents])
    outgoing = messages_for(incidents, cfg, now, evidence)
    if outgoing:
        store.insert_missing(
            spark,
            settings.table("ops", "notification_outbox"),
            [enqueue_row(message, cfg, now) for message in outgoing],
            "dedup_key",
        )

    entries = due_entries(spark, settings, now)
    if entries:
        from databricks.sdk import WorkspaceClient

        token = WorkspaceClient().dbutils.secrets.get(settings.secret_scope, "whatsapp_token")
        client = WhatsAppClient(phone_number_id=cfg.phone_number_id, token=token)
        rows = [dispatch_message(client, entry, cfg, now) for entry in entries]
        store.merge_rows(spark, settings.table("ops", "notification_outbox"), rows, ["dedup_key"])
        for row in rows:
            link_incident(spark, settings, row)
            record_dlq(spark, settings, row, now)
        logger.info("notify enviou %s mensagem(ns)", len(rows))

    purge_expired(spark, settings, now)


if __name__ == "__main__":
    main()
