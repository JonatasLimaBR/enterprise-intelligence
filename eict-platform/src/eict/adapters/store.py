from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from eict.domain.models import Evidence, Hypothesis, Incident, Run, RunProfile, TimelineEntry


def ensure_utc(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def utc_row(record: dict) -> dict:
    return {key: ensure_utc(value) for key, value in record.items()}


def rows_to_dicts(rows: Any) -> list[dict]:
    return [utc_row(row.asDict(recursive=True)) for row in rows]


def query(spark: Any, sql: str) -> list[dict]:
    return rows_to_dicts(spark.sql(sql).collect())


def align_rows(column_names: list[str], rows: list[dict]) -> list[dict]:
    return [{name: row.get(name) for name in column_names} for row in rows]


def frame_for(spark: Any, table: str, rows: list[dict]):
    schema = spark.table(table).schema
    names = [field.name for field in schema.fields]
    return spark.createDataFrame(align_rows(names, rows), schema=schema)


def append_rows(spark: Any, table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    frame_for(spark, table, rows).write.mode("append").saveAsTable(table)
    return len(rows)


def merge_rows(spark: Any, table: str, rows: list[dict], keys: list[str]) -> int:
    if not rows:
        return 0
    view = f"staged_{abs(hash(table)) % 10_000}"
    frame_for(spark, table, rows).createOrReplaceTempView(view)
    condition = " AND ".join(f"target.{key} = source.{key}" for key in keys)
    spark.sql(
        f"""
        MERGE INTO {table} AS target
        USING {view} AS source
        ON {condition}
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )
    spark.catalog.dropTempView(view)
    return len(rows)


def insert_missing(spark: Any, table: str, rows: list[dict], key: str) -> int:
    if not rows:
        return 0
    view = f"incoming_{abs(hash(table)) % 10_000}"
    frame_for(spark, table, rows).createOrReplaceTempView(view)
    spark.sql(
        f"""
        MERGE INTO {table} AS target
        USING {view} AS source
        ON target.{key} = source.{key}
        WHEN NOT MATCHED THEN INSERT *
        """
    )
    spark.catalog.dropTempView(view)
    return len(rows)


def incident_row(incident: Incident) -> dict:
    return {
        "correlation_key": incident.correlation_key,
        "incident_id": incident.incident_id,
        "tenant_id": incident.tenant_id,
        "job_id": incident.job_id,
        "type": incident.type,
        "state": incident.state,
        "severity": incident.severity,
        "first_run_id": incident.first_run_id,
        "last_run_id": incident.last_run_id,
        "detected_at": incident.detected_at,
        "updated_at": incident.updated_at,
        "affected_assets": list(incident.affected_assets),
        "ticket_refs": list(incident.ticket_refs),
        "version": incident.version,
    }


def timeline_row(entry: TimelineEntry) -> dict:
    return {
        "entry_id": entry.entry_id,
        "incident_id": entry.incident_id,
        "at": entry.at,
        "kind": entry.kind,
        "summary": entry.summary,
        "evidence_ids": list(entry.evidence_ids),
        "actor": entry.actor,
    }


def evidence_row(incident_id: str, evidence: Evidence) -> dict:
    return {
        "evidence_id": evidence.evidence_id,
        "incident_id": incident_id,
        "kind": evidence.kind,
        "source_ref": evidence.source_ref,
        "observed_at": evidence.observed_at,
        "summary": evidence.summary,
        "value_json": str(evidence.value) if evidence.value is not None else None,
        "hash": evidence.hash,
    }


def hypothesis_row(incident_id: str, hypothesis: Hypothesis) -> dict:
    return {
        "hypothesis_id": hypothesis.hypothesis_id,
        "incident_id": incident_id,
        "code": hypothesis.code,
        "statement": hypothesis.statement,
        "rank": hypothesis.rank,
        "confidence": float(hypothesis.confidence),
        "supporting": list(hypothesis.supporting),
        "contradicting": list(hypothesis.contradicting),
        "missing": list(hypothesis.missing),
        "status": hypothesis.status,
        "policy_version": hypothesis.policy_version,
        "reviewed_by": hypothesis.reviewed_by,
        "reviewed_at": hypothesis.reviewed_at,
    }


def to_run(record: dict) -> Run:
    return Run(
        run_id=record["run_id"],
        job_id=record["job_id"],
        start_time=record["start_time"],
        end_time=record["end_time"],
        duration_s=float(record["duration_s"]),
        result_state=record["result_state"],
        git_sha=record.get("git_sha"),
        env_hash=record.get("env_hash"),
        input_rows=record.get("input_rows"),
        job_parameters=record.get("job_parameters") or {},
    )


def to_run_profile(record: dict) -> RunProfile | None:
    if not record or record.get("skew_ratio") is None:
        return None
    return RunProfile(
        run_id=record["run_id"],
        key=record.get("key") or "unknown",
        left_rows=int(record.get("left_rows") or 0),
        right_rows=int(record.get("right_rows") or 0),
        distinct_keys=int(record.get("distinct_keys") or 0),
        max_key_rows=int(record.get("max_key_rows") or 0),
        median_key_rows=int(record.get("median_key_rows") or 0),
        skew_ratio=float(record["skew_ratio"]),
        top_key_share=float(record.get("top_key_share") or 0.0),
        hot_key=str(record.get("hot_key") or ""),
        plan_operators=tuple(record.get("plan_operators") or ()),
        git_sha=record.get("git_sha"),
        source_ref=record.get("source_ref"),
    )


def checkpoint_row(connector: str, cursor: str, at: datetime, error: str | None = None) -> dict:
    return {
        "connector": connector,
        "cursor": cursor,
        "last_success_at": at if error is None else None,
        "last_error": error,
    }
