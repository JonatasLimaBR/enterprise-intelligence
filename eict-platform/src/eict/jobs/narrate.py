from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from eict.adapters import store
from eict.adapters.llm import NarratorClient, enable_tracing
from eict.config import Settings, parse_settings
from eict.domain.models import ACTIVE_INCIDENT_STATES, Evidence, Hypothesis, Incident, stable_id
from eict.domain.narrative import build_facts, build_prompt, narrate

logger = logging.getLogger(__name__)

MLFLOW_EXPERIMENT = "/Shared/eict-narrator"


def pending_incidents(spark: Any, settings: Settings) -> list[Incident]:
    states = ", ".join(f"'{state}'" for state in sorted(ACTIVE_INCIDENT_STATES))
    records = store.query(
        spark,
        f"""
        SELECT i.*
        FROM {settings.table('ops', 'incidents')} i
        LEFT JOIN (
            SELECT incident_id, MAX(created_at) AS last_narrated
            FROM {settings.table('ops', 'narratives')}
            GROUP BY incident_id
        ) n ON n.incident_id = i.incident_id
        WHERE i.state IN ({states})
          AND (n.last_narrated IS NULL OR n.last_narrated < i.updated_at)
        """,
    )
    return [
        Incident(
            incident_id=record["incident_id"],
            correlation_key=record["correlation_key"],
            tenant_id=record["tenant_id"],
            subject=record["subject"],
            type=record["type"],
            state=record["state"],
            severity=record["severity"],
            first_run_id=record["first_run_id"],
            last_run_id=record["last_run_id"],
            detected_at=record["detected_at"],
            updated_at=record["updated_at"],
            affected_assets=tuple(record.get("affected_assets") or ()),
            ticket_refs=tuple(record.get("ticket_refs") or ()),
            declared_consumers=tuple(record.get("declared_consumers") or ()),
            version=int(record.get("version") or 1),
        )
        for record in records
    ]


def load_hypotheses(spark: Any, settings: Settings, incident_id: str) -> list[Hypothesis]:
    records = store.query(
        spark,
        f"SELECT * FROM {settings.table('ops', 'hypotheses')} "
        f"WHERE incident_id = '{incident_id}' ORDER BY rank",
    )
    return [
        Hypothesis(
            hypothesis_id=record["hypothesis_id"],
            code=record["code"],
            statement=record["statement"],
            confidence=float(record["confidence"]),
            supporting=tuple(record.get("supporting") or ()),
            contradicting=tuple(record.get("contradicting") or ()),
            missing=tuple(record.get("missing") or ()),
            rank=int(record.get("rank") or 0),
            status=record.get("status") or "proposed",
            policy_version=record.get("policy_version") or "",
        )
        for record in records
    ]


def load_evidence(spark: Any, settings: Settings, incident_id: str) -> list[Evidence]:
    records = store.query(
        spark,
        f"SELECT * FROM {settings.table('ops', 'evidence')} WHERE incident_id = '{incident_id}'",
    )
    return [
        Evidence(
            evidence_id=record["evidence_id"],
            kind=record["kind"],
            source_ref=record["source_ref"],
            observed_at=record["observed_at"],
            summary=record["summary"],
            value=record.get("value_json"),
            hash=record.get("hash") or "",
        )
        for record in records
    ]


def narrate_incident(
    client: NarratorClient | None,
    incident: Incident,
    hypotheses: list[Hypothesis],
    evidence: list[Evidence],
) -> dict:
    facts = build_facts(evidence)
    raw = None
    model = None
    trace_id = None
    if client is not None and facts:
        response = client.complete(build_prompt(incident, hypotheses, facts))
        raw = response.content
        model = response.model
        trace_id = response.trace_id
    result = narrate(raw, incident, hypotheses, facts)
    return {
        "narrative_id": stable_id("nar", incident.incident_id, str(incident.version)),
        "incident_id": incident.incident_id,
        "source": result.source,
        "sentences_json": json.dumps(
            [sentence.model_dump() for sentence in result.sentences], ensure_ascii=False
        ),
        "model": model,
        "trace_id": trace_id,
        "rejected_reason": result.rejected_reason,
        "created_at": datetime.now(UTC),
    }


def main(argv: list[str] | None = None) -> None:
    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    enable_tracing(MLFLOW_EXPERIMENT)
    client = NarratorClient(workspace=WorkspaceClient(), endpoint=settings.llm_endpoint)

    rows = []
    for incident in pending_incidents(spark, settings):
        hypotheses = load_hypotheses(spark, settings, incident.incident_id)
        evidence = load_evidence(spark, settings, incident.incident_id)
        row = narrate_incident(client, incident, hypotheses, evidence)
        rows.append(row)
        if row["rejected_reason"]:
            logger.warning(
                "narrative rejected for %s: %s", incident.incident_id, row["rejected_reason"]
            )
    store.merge_rows(spark, settings.table("ops", "narratives"), rows, ["narrative_id"])
    logger.info("narrated %s incidents", len(rows))


if __name__ == "__main__":
    main()
