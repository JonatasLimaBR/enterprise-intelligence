from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from eict.domain.models import Evidence, Hypothesis, Incident, Run, RunProfile, TimelineEntry, stable_id


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
    resultado = spark.sql(
        f"""
        MERGE INTO {table} AS target
        USING {view} AS source
        ON target.{key} = source.{key}
        WHEN NOT MATCHED THEN INSERT *
        """
    )
    spark.catalog.dropTempView(view)
    return inserted_count(resultado, len(rows))


def inserted_count(merge_result: Any, fallback: int) -> int:
    """Linhas de fato inseridas, pela métrica que o MERGE devolve.

    Devolver `len(rows)` dizia "20 novos" num backfill repetido que não inseriu nada.
    Sem a métrica (ambiente que não a expõe), recua para o total enviado.
    """
    try:
        linha = merge_result.collect()[0]
        return int(linha["num_inserted_rows"])
    except Exception:
        return fallback


def incident_row(incident: Incident) -> dict:
    return {
        "correlation_key": incident.correlation_key,
        "incident_id": incident.incident_id,
        "tenant_id": incident.tenant_id,
        "subject": incident.subject,
        "job_id": incident.subject,  # legado: mantido até nenhum leitor usar
        "type": incident.type,
        "state": incident.state,
        "severity": incident.severity,
        "first_run_id": incident.first_run_id,
        "last_run_id": incident.last_run_id,
        "detected_at": incident.detected_at,
        "updated_at": incident.updated_at,
        "affected_assets": list(incident.affected_assets),
        "ticket_refs": list(incident.ticket_refs),
        "declared_consumers": list(incident.declared_consumers),
        "impact_score": float(incident.impact_score),
        "impact_policy_version": incident.impact_policy_version,
        "escalated_from": incident.escalated_from,
        "escalation_reason": incident.escalation_reason,
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


def metric_row(observed, source_sha: str, observed_at) -> dict:
    return {
        "observation_id": stable_id(
            "obs", observed.asset, observed.metric_id, observed.source_path,
            str(observed.source_line),
        ),
        "metric_id": observed.metric_id,
        "asset": observed.asset,
        "source_path": observed.source_path,
        "source_line": int(observed.source_line),
        "source_sha": source_sha,
        "formula_raw": observed.formula_raw,
        "formula_hash": observed.formula_hash,
        "grain": list(observed.grain),
        "extraction_status": observed.status,
        "extraction_detail": observed.detail,
        "observed_at": observed_at,
    }


def ontology_row(edge) -> dict:
    return {
        "edge_id": edge.edge_id,
        "subject": edge.subject,
        "predicate": edge.predicate,
        "object": edge.object,
        "origin": edge.origin,
        "status": edge.status,
        "confidence": float(edge.confidence),
        "observed_at": edge.observed_at,
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
        setup_s=_optional_float(record.get("setup_s")),
        execution_s=_optional_float(record.get("execution_s")),
    )


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


def monitored_job_row(job, active: tuple | None, observed_at) -> dict:
    from eict.domain.producers import normalize

    return {
        "job_id": job.job_id,
        "name": job.name,
        "normalized_name": normalize(job.name),
        "active_run_id": active[0] if active else None,
        "active_since": active[1] if active else None,
        "observed_at": observed_at,
    }


def sla_prediction_row(assessment, predicted_at, policy_version: str) -> dict:
    return {
        "prediction_id": stable_id(
            "slap", assessment.asset, assessment.slo_kind, str(assessment.deadline), predicted_at.isoformat()
        ),
        "asset": assessment.asset,
        "slo_kind": assessment.slo_kind,
        "deadline": assessment.deadline,
        "predicted_at": predicted_at,
        "remaining_s": assessment.remaining_s,
        "slack_s": assessment.slack_s,
        "klass": assessment.klass,
        "producer_job_id": assessment.producer_job_id or None,
        "producer_state": assessment.producer_state or None,
        "policy_version": policy_version,
        "outcome": None,
        "outcome_at": None,
    }


def regime_row(regime) -> dict:
    return {
        "regime_id": regime.regime_id,
        "job_id": regime.job_id,
        "effective_from_at": regime.effective_from_at,
        "effective_from_sha": regime.effective_from_sha or None,
        "origin": regime.origin,
        "decided_by": regime.decided_by,
        "identity_source": regime.identity_source,
        "reason": regime.reason,
        "incident_id": regime.incident_id or None,
        "created_at": regime.created_at,
    }


def to_regime(record: dict):
    from eict.domain.regimes import Regime

    return Regime(
        regime_id=record["regime_id"],
        job_id=record["job_id"],
        origin=record.get("origin") or "",
        decided_by=record.get("decided_by") or "",
        reason=record.get("reason") or "",
        identity_source=record.get("identity_source") or "",
        effective_from_at=record.get("effective_from_at"),
        effective_from_sha=record.get("effective_from_sha") or "",
        incident_id=record.get("incident_id") or "",
        created_at=record.get("created_at"),
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
