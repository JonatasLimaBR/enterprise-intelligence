from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from eict.adapters import store
from eict.adapters.jira import JiraClient, JiraPermanentError, JiraRetryableError, label_for
from eict.config import Settings, parse_settings

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BACKOFF_MINUTES = (1, 2, 4, 8, 16)
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class OutboxEntry:
    correlation_key: str
    incident_id: str
    attempts: int
    summary: str
    description: str


def due_entries(spark: Any, settings: Settings, now: datetime) -> list[OutboxEntry]:
    records = store.query(
        spark,
        f"""
        SELECT * FROM {settings.table('ops', 'ticket_outbox')}
        WHERE status = '{STATUS_PENDING}'
          AND (next_attempt_at IS NULL OR next_attempt_at <= TIMESTAMP '{now.isoformat(sep=" ", timespec="seconds")}')
        """,
    )
    return [
        OutboxEntry(
            correlation_key=record["correlation_key"],
            incident_id=record["incident_id"],
            attempts=int(record.get("attempts") or 0),
            summary=record.get("summary") or "",
            description=record.get("description") or "",
        )
        for record in records
    ]


def next_backoff(attempts: int) -> timedelta:
    index = min(attempts, len(BACKOFF_MINUTES) - 1)
    return timedelta(minutes=BACKOFF_MINUTES[index])


def dispatch_entry(client: JiraClient, entry: OutboxEntry, now: datetime) -> dict:
    label = label_for(entry.correlation_key)
    try:
        issue = client.ensure_issue(label, entry.summary, entry.description)
    except JiraRetryableError as exc:
        return _retry_row(entry, now, str(exc)[:500])
    except JiraPermanentError as exc:
        return _failed_row(entry, now, str(exc)[:500])
    return {
        "correlation_key": entry.correlation_key,
        "incident_id": entry.incident_id,
        "status": STATUS_SENT,
        "attempts": entry.attempts + 1,
        "next_attempt_at": None,
        "last_error": None,
        "issue_key": issue.key,
        "issue_url": issue.url,
        "summary": entry.summary,
        "description": entry.description,
        "updated_at": now,
    }


def _retry_row(entry: OutboxEntry, now: datetime, error: str) -> dict:
    attempts = entry.attempts + 1
    exhausted = attempts >= MAX_ATTEMPTS
    return {
        "correlation_key": entry.correlation_key,
        "incident_id": entry.incident_id,
        "status": STATUS_FAILED if exhausted else STATUS_PENDING,
        "attempts": attempts,
        "next_attempt_at": None if exhausted else now + next_backoff(attempts),
        "last_error": error,
        "issue_key": None,
        "issue_url": None,
        "summary": entry.summary,
        "description": entry.description,
        "updated_at": now,
    }


def _failed_row(entry: OutboxEntry, now: datetime, error: str) -> dict:
    return {
        "correlation_key": entry.correlation_key,
        "incident_id": entry.incident_id,
        "status": STATUS_FAILED,
        "attempts": entry.attempts + 1,
        "next_attempt_at": None,
        "last_error": error,
        "issue_key": None,
        "issue_url": None,
        "summary": entry.summary,
        "description": entry.description,
        "updated_at": now,
    }


def link_incident(spark: Any, settings: Settings, row: dict) -> None:
    if row["status"] != STATUS_SENT:
        return
    spark.sql(
        f"""
        UPDATE {settings.table('ops', 'incidents')}
        SET ticket_refs = array_distinct(array_union(coalesce(ticket_refs, array()), array('{row["issue_url"]}'))),
            version = version + 1
        WHERE correlation_key = '{row["correlation_key"]}'
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
                "dlq_id": f"jira-{row['correlation_key']}-{row['attempts']}",
                "source": "jira",
                "payload": row["summary"],
                "error": row["last_error"],
                "at": now,
            }
        ],
    )


def main(argv: list[str] | None = None) -> None:
    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    if not settings.jira_base_url or not settings.jira_project:
        logger.info("jira not configured; skipping dispatch")
        return

    spark = SparkSession.builder.getOrCreate()
    workspace = WorkspaceClient()
    now = datetime.now(UTC)
    client = JiraClient(
        base_url=settings.jira_base_url,
        email=workspace.dbutils.secrets.get(settings.secret_scope, "jira_email"),
        token=workspace.dbutils.secrets.get(settings.secret_scope, "jira_token"),
        project_key=settings.jira_project,
    )

    rows = [dispatch_entry(client, entry, now) for entry in due_entries(spark, settings, now)]
    if not rows:
        return
    store.merge_rows(spark, settings.table("ops", "ticket_outbox"), rows, ["correlation_key"])
    for row in rows:
        link_incident(spark, settings, row)
        record_dlq(spark, settings, row, now)
    logger.info("dispatched %s outbox entries", len(rows))


if __name__ == "__main__":
    main()
