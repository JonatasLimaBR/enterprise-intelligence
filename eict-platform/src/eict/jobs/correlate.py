from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from eict.adapters import capabilities as capability_probe
from eict.adapters import store
from eict.adapters.jira import label_for
from eict.config import Settings, parse_settings
from eict.domain import baseline as baseline_rules
from eict.domain import hypotheses as hypothesis_rules
from eict.domain.cost import BillingFact, incremental_cost
from eict.domain.incidents import RUNTIME_REGRESSION, Review, apply_reviews, detection_entry, open_or_update
from eict.domain.models import ACTIVE_INCIDENT_STATES, Change, Incident, RunFeatures

logger = logging.getLogger(__name__)

CORRELATOR_CONNECTOR = "correlator"
CAUSAL_WINDOW = timedelta(days=7)
OUTBOX_PENDING = "pending"


def load_features(spark: Any, settings: Settings) -> list[RunFeatures]:
    records = store.query(
        spark,
        f"SELECT * FROM {settings.table('gold', 'run_features')} ORDER BY end_time",
    )
    return [RunFeatures(run=store.to_run(record), profile=store.to_run_profile(record)) for record in records]


def load_changes(spark: Any, settings: Settings) -> list[Change]:
    records = store.query(
        spark, f"SELECT * FROM {settings.table('silver', 'changes')} ORDER BY committed_at DESC"
    )
    return [
        Change(
            sha=record["sha"],
            repo=record.get("repo") or "",
            author=record.get("author") or "",
            committed_at=record["committed_at"],
            message=record.get("message") or "",
            files=tuple(record.get("files") or ()),
            patch=record.get("patch") or "",
        )
        for record in records
    ]


def load_active_incidents(spark: Any, settings: Settings) -> list[Incident]:
    states = ", ".join(f"'{state}'" for state in sorted(ACTIVE_INCIDENT_STATES))
    records = store.query(
        spark,
        f"SELECT * FROM {settings.table('ops', 'incidents')} WHERE state IN ({states})",
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


def load_reviews(spark: Any, settings: Settings) -> list[Review]:
    records = store.query(spark, f"SELECT * FROM {settings.table('ops', 'hypothesis_reviews')}")
    return [
        Review(
            hypothesis_id=record["hypothesis_id"],
            decision=record["decision"],
            reviewer=record["reviewer"],
            at=record["at"],
            note=record.get("note") or "",
        )
        for record in records
    ]


def changes_in_window(changes: list[Change], healthy: RunFeatures | None, current: RunFeatures) -> list[Change]:
    window_start = healthy.run.end_time if healthy else current.run.start_time - CAUSAL_WINDOW
    in_window = [
        change
        for change in changes
        if window_start <= change.committed_at <= current.run.start_time
    ]
    deployed = [change for change in changes if change.sha == current.run.git_sha]
    ordered = deployed + [change for change in in_window if change.sha not in {c.sha for c in deployed}]
    return ordered


def downstream_assets(spark: Any, settings: Settings, job_id: str, available: bool) -> tuple[str, ...]:
    if not available:
        return ()
    try:
        records = store.query(
            spark,
            f"""
            SELECT DISTINCT entity_type, entity_id, target_table_full_name
            FROM {capability_probe.TABLE_LINEAGE}
            WHERE source_table_full_name IS NOT NULL
              AND event_time > current_timestamp() - INTERVAL 30 DAYS
              AND source_table_full_name LIKE '{settings.catalog}.{settings.schema_prefix}workload.%'
            """,
        )
    except Exception as exc:
        logger.warning("lineage query failed: %s", exc)
        return ()
    assets = {
        record.get("target_table_full_name") or f"{record.get('entity_type')}/{record.get('entity_id')}"
        for record in records
    }
    return tuple(sorted(asset for asset in assets if asset))


def billing_fact(spark: Any, run_id: str, available: bool) -> BillingFact | None:
    if not available:
        return None
    try:
        records = store.query(
            spark,
            f"""
            SELECT SUM(u.usage_quantity) AS dbus,
                   SUM(u.usage_quantity * p.pricing.default) AS list_cost_usd
            FROM {capability_probe.BILLING_USAGE} u
            JOIN {capability_probe.BILLING_PRICES} p
              ON u.sku_name = p.sku_name AND p.price_end_time IS NULL
            WHERE u.usage_metadata.job_run_id = '{run_id}'
            """,
        )
    except Exception as exc:
        logger.warning("billing query failed: %s", exc)
        return None
    if not records or records[0].get("dbus") is None:
        return None
    return BillingFact(
        run_id=run_id,
        dbus=float(records[0]["dbus"]),
        list_cost_usd=float(records[0]["list_cost_usd"] or 0.0),
        source_ref=capability_probe.BILLING_USAGE,
    )


def correlate(
    spark: Any,
    settings: Settings,
    features: list[RunFeatures],
    changes: list[Change],
    incidents: list[Incident],
    reviews: list[Review],
    capabilities: list[capability_probe.Capability],
    now: datetime,
) -> list[Incident]:
    history = [item.run for item in features]
    by_run_id = {item.run_id: item for item in features}
    lineage_available = capability_probe.status_of(capabilities, capability_probe.TABLE_LINEAGE)
    billing_available = capability_probe.status_of(capabilities, capability_probe.BILLING_USAGE)
    touched: list[Incident] = []
    incident_run_ids = _runs_under_incident(incidents)

    for current in features:
        verdict = baseline_rules.evaluate(current.run, history, incident_run_ids)
        if not verdict.is_regression or verdict.baseline is None:
            incident_run_ids = incident_run_ids - {current.run_id}
            continue

        incident, created = open_or_update(
            incidents, settings.tenant_id, current.run.job_id, RUNTIME_REGRESSION, current.run
        )
        incident_run_ids = incident_run_ids | {current.run_id}
        healthy_run = baseline_rules.last_healthy_run(history, current.run, incident_run_ids)
        healthy = by_run_id.get(healthy_run.run_id) if healthy_run else None
        analysis = hypothesis_rules.analyze(
            current,
            healthy,
            changes_in_window(changes, healthy, current),
            now,
            scope_id=incident.incident_id,
        )
        reviewed, review_entries = apply_reviews(list(analysis.hypotheses), reviews)

        assets = downstream_assets(spark, settings, current.run.job_id, lineage_available)
        incident = incident.with_assets(assets) if assets else incident

        _persist_incident(
            spark, settings, incident, current.run, verdict.baseline, created, analysis, reviewed, review_entries
        )
        _persist_cost(
            spark, settings, incident, current, history, billing_available, now
        )
        _queue_ticket(spark, settings, incident, current, reviewed, now)

        incidents = [item for item in incidents if item.correlation_key != incident.correlation_key]
        incidents.append(incident)
        touched.append(incident)

    return touched


def _runs_under_incident(incidents: list[Incident]) -> frozenset[str]:
    attributed: set[str] = set()
    for incident in incidents:
        if incident.is_active:
            attributed.update({incident.first_run_id, incident.last_run_id})
    return frozenset(attributed)


def _persist_incident(
    spark, settings, incident, run, baseline, created, analysis, hypotheses, review_entries
) -> None:
    store.merge_rows(
        spark, settings.table("ops", "incidents"), [store.incident_row(incident)], ["correlation_key"]
    )
    store.insert_missing(
        spark,
        settings.table("ops", "evidence"),
        [store.evidence_row(incident.incident_id, item) for item in analysis.evidence],
        "evidence_id",
    )
    store.merge_rows(
        spark,
        settings.table("ops", "hypotheses"),
        [store.hypothesis_row(incident.incident_id, item) for item in hypotheses],
        ["hypothesis_id"],
    )
    entries = [detection_entry(incident, run, baseline, created), *review_entries]
    store.insert_missing(
        spark,
        settings.table("ops", "incident_timeline"),
        [store.timeline_row(entry) for entry in entries],
        "entry_id",
    )


def _persist_cost(spark, settings, incident, current, history, billing_available, now) -> None:
    baseline_runs = [
        run for run in history if run.succeeded and run.end_time < current.run.start_time
    ][-5:]
    facts = [
        fact
        for fact in (billing_fact(spark, run.run_id, billing_available) for run in baseline_runs)
        if fact is not None
    ]
    cost = incremental_cost(
        run_id=current.run_id,
        run_end=current.run.end_time,
        now=now,
        run_fact=billing_fact(spark, current.run_id, billing_available),
        baseline_facts=facts,
        billing_available=billing_available,
    )
    store.merge_rows(
        spark,
        settings.table("ops", "run_cost"),
        [
            {
                "run_id": cost.run_id,
                "incident_id": incident.incident_id,
                "status": cost.status,
                "dbus": cost.dbus,
                "list_cost_usd": cost.list_cost_usd,
                "baseline_cost_usd": cost.baseline_cost_usd,
                "incremental_cost_usd": cost.incremental_cost_usd,
                "source_ref": cost.source_ref,
                "updated_at": now,
            }
        ],
        ["run_id"],
    )


def _queue_ticket(spark, settings, incident, current, hypotheses, now) -> None:
    if not settings.jira_base_url or not settings.jira_project:
        return
    top = min(hypotheses, key=lambda item: item.rank) if hypotheses else None
    summary = f"[EICT] Regressão de runtime no job {incident.job_id}"
    description = json.dumps(
        {
            "incident_id": incident.incident_id,
            "correlation_key": incident.correlation_key,
            "run_id": current.run_id,
            "duration_s": current.run.duration_s,
            "top_hypothesis": top.statement if top else None,
            "confidence": top.confidence if top else None,
            "affected_assets": list(incident.affected_assets),
        },
        ensure_ascii=False,
        indent=2,
    )
    store.insert_missing(
        spark,
        settings.table("ops", "ticket_outbox"),
        [
            {
                "correlation_key": incident.correlation_key,
                "incident_id": incident.incident_id,
                "status": OUTBOX_PENDING,
                "attempts": 0,
                "next_attempt_at": now,
                "last_error": None,
                "issue_key": None,
                "issue_url": None,
                "summary": summary,
                "description": f"{description}\n\nlabel: {label_for(incident.correlation_key)}",
                "updated_at": now,
            }
        ],
        "correlation_key",
    )


PRODUCER_WINDOW_HOURS = 6


def producer_states(spark, settings, producers: set[str], now) -> dict[str, bool]:
    """Para cada produtor declarado, diz se ele rodou com sucesso na janela recente.

    Sem isso, a hipótese de pipeline parado nunca pontua — e ela costuma ser a resposta
    certa quando a violação é de freshness.
    """
    if not producers:
        return {}
    limite = (now - timedelta(hours=PRODUCER_WINDOW_HOURS)).isoformat(sep=" ", timespec="seconds")
    try:
        records = store.query(
            spark,
            f"""
            SELECT job_name, max(end_time) AS ultima, max_by(result_state, end_time) AS estado
            FROM {settings.table('gold', 'run_features')}
            WHERE job_name IS NOT NULL AND end_time >= TIMESTAMP '{limite}'
            GROUP BY job_name
            """,
        )
    except Exception as exc:
        logger.warning("estado dos produtores indisponível: %s", exc)
        return {}

    estados: dict[str, bool] = {}
    for producer in producers:
        correspondentes = [
            record for record in records if producer.lower() in (record["job_name"] or "").lower()
        ]
        estados[producer] = any(
            record["estado"] == "SUCCESS" for record in correspondentes
        )
    return estados


def correlate_quality_incidents(spark, settings, incidents, changes, now) -> int:
    """Roda o correlator de qualidade sobre os resultados de regra recentes."""
    from eict.adapters.contract_loader import load_directory
    from eict.jobs import correlate_quality as quality_correlator
    from eict.jobs.quality import contracts_dir

    results = quality_correlator.load_recent_results(spark, settings, now)
    if not results:
        return 0

    contracts = {
        contract.asset: contract for contract in load_directory(contracts_dir(settings)).active
    }
    payload = quality_correlator.QualityInput(
        results=results,
        contracts=contracts,
        changes=changes,
        producer_states=producer_states(
            spark, settings, {contract.producer for contract in contracts.values()}, now
        ),
    )
    touched, entries, evidences, hypotheses = quality_correlator.correlate_quality(
        payload, incidents, settings.tenant_id, now
    )
    quality_correlator.persist(spark, settings, touched, entries, evidences, hypotheses)
    return len(touched)


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    from eict.jobs.bootstrap_ops import ensure_gold_view

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    ensure_gold_view(spark, settings)
    now = datetime.now(UTC)
    capabilities = [
        capability_probe.Capability(
            capability=record["capability"],
            status=record["status"],
            detail=record.get("detail") or "",
            checked_at=record["checked_at"],
        )
        for record in store.query(spark, f"SELECT * FROM {settings.table('ops', 'capabilities')}")
    ]
    changes = load_changes(spark, settings)
    touched = correlate(
        spark,
        settings,
        load_features(spark, settings),
        changes,
        load_active_incidents(spark, settings),
        load_reviews(spark, settings),
        capabilities,
        now,
    )
    quality_touched = correlate_quality_incidents(
        spark, settings, load_active_incidents(spark, settings), changes, now
    )
    logger.info(
        "correlacionados: %s incidentes de runtime, %s de qualidade",
        len(touched),
        quality_touched,
    )


if __name__ == "__main__":
    main()
