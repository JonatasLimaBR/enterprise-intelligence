from __future__ import annotations

import logging
from typing import Any

from eict.config import Settings, parse_settings

logger = logging.getLogger(__name__)

SCHEMAS = ("bronze", "silver", "gold", "ops", "platform")

TABLES: dict[tuple[str, str], str] = {
    ("bronze", "observations"): """
        id STRING NOT NULL,
        specversion STRING,
        source STRING,
        type STRING,
        subject STRING,
        time TIMESTAMP,
        tenant_id STRING,
        environment STRING,
        classification STRING,
        schema_version INT,
        trace_id STRING,
        data STRING,
        content_hash STRING
    """,
    ("ops", "incidents"): """
        correlation_key STRING NOT NULL,
        incident_id STRING,
        tenant_id STRING,
        subject STRING,
        type STRING,
        state STRING,
        severity STRING,
        first_run_id STRING,
        last_run_id STRING,
        detected_at TIMESTAMP,
        updated_at TIMESTAMP,
        affected_assets ARRAY<STRING>,
        ticket_refs ARRAY<STRING>,
        declared_consumers ARRAY<STRING>,
        impact_score DOUBLE,
        impact_policy_version STRING,
        escalated_from STRING,
        escalation_reason STRING,
        version INT
    """,
    ("ops", "lineage_graph"): """
        edge_id STRING NOT NULL,
        source_asset STRING,
        target_asset STRING,
        entity_type STRING,
        entity_id STRING,
        first_seen TIMESTAMP,
        last_seen TIMESTAMP,
        schema_fingerprint STRING,
        previous_fingerprint STRING,
        fingerprint_changed_at TIMESTAMP,
        observed_cycles BIGINT
    """,
    ("ops", "metrics"): """
        observation_id STRING NOT NULL,
        metric_id STRING,
        asset STRING,
        source_path STRING,
        source_line INT,
        source_sha STRING,
        formula_raw STRING,
        formula_hash STRING,
        grain ARRAY<STRING>,
        extraction_status STRING,
        extraction_detail STRING,
        observed_at TIMESTAMP
    """,
    ("ops", "ontology_edges"): """
        edge_id STRING NOT NULL,
        subject STRING,
        predicate STRING,
        object STRING,
        origin STRING,
        status STRING,
        confidence DOUBLE,
        observed_at TIMESTAMP
    """,
    ("ops", "incident_timeline"): """
        entry_id STRING NOT NULL,
        incident_id STRING,
        at TIMESTAMP,
        kind STRING,
        summary STRING,
        evidence_ids ARRAY<STRING>,
        actor STRING
    """,
    ("ops", "evidence"): """
        evidence_id STRING NOT NULL,
        incident_id STRING,
        kind STRING,
        source_ref STRING,
        observed_at TIMESTAMP,
        summary STRING,
        value_json STRING,
        hash STRING
    """,
    ("ops", "hypotheses"): """
        hypothesis_id STRING NOT NULL,
        incident_id STRING,
        code STRING,
        statement STRING,
        rank INT,
        confidence DOUBLE,
        supporting ARRAY<STRING>,
        contradicting ARRAY<STRING>,
        missing ARRAY<STRING>,
        status STRING,
        policy_version STRING,
        reviewed_by STRING,
        reviewed_at TIMESTAMP
    """,
    # Gestão de problemas: cada tabela tem um só dono. O ciclo recalcula os candidatos; o registro
    # humano (owner, correção) o ciclo nunca escreve — o MERGE com UPDATE SET * o apagaria.
    ("ops", "problem_candidates"): """
        problem_id STRING NOT NULL,
        signature STRING,
        type STRING,
        subject STRING,
        cause STRING,
        incident_ids ARRAY<STRING>,
        incident_count INT,
        first_detected_at TIMESTAMP,
        last_detected_at TIMESTAMP,
        impact_score_sum DOUBLE,
        open_hours DOUBLE,
        status STRING,
        efficacy_detail STRING,
        policy_version STRING,
        evaluated_at TIMESTAMP
    """,
    ("ops", "problem_records"): """
        problem_id STRING NOT NULL,
        signature STRING,
        owner STRING,
        due_at TIMESTAMP,
        success_metric STRING,
        known_error STRING,
        workaround STRING,
        fix_description STRING,
        fix_at TIMESTAMP,
        promoted_by STRING,
        promoted_at TIMESTAMP
    """,
    ("ops", "recommendations"): """
        recommendation_id STRING NOT NULL,
        incident_id STRING,
        hypothesis_id STRING,
        kind STRING,
        text STRING,
        basis STRING,
        evidence_ids ARRAY<STRING>,
        owner_role STRING,
        policy_version STRING,
        created_at TIMESTAMP
    """,
    ("ops", "recommendation_reviews"): """
        review_id STRING NOT NULL,
        recommendation_id STRING,
        incident_id STRING,
        decision STRING,
        reviewer STRING,
        at TIMESTAMP,
        note STRING
    """,
    ("ops", "executive_summary"): """
        metric_id STRING NOT NULL,
        label STRING,
        value DOUBLE,
        unit STRING,
        window STRING,
        source STRING,
        n INT,
        formula STRING,
        confidence STRING,
        detail STRING,
        policy_version STRING,
        computed_at TIMESTAMP
    """,
    ("ops", "connector_health"): """
        connector STRING NOT NULL,
        status STRING,
        retrying INT,
        quarantined INT,
        last_success_at TIMESTAMP,
        last_error STRING,
        detail STRING,
        evaluated_at TIMESTAMP
    """,
    ("ops", "audit_log"): """
        seq BIGINT,
        audit_id STRING NOT NULL,
        at TIMESTAMP,
        actor STRING,
        identity_source STRING,
        roles STRING,
        action STRING,
        target STRING,
        decision STRING,
        reason STRING,
        prev_hash STRING,
        hash STRING
    """,
    ("ops", "monitored_jobs"): """
        job_id STRING NOT NULL,
        name STRING,
        normalized_name STRING,
        active_run_id STRING,
        active_since TIMESTAMP,
        observed_at TIMESTAMP
    """,
    ("ops", "sla_predictions"): """
        prediction_id STRING NOT NULL,
        asset STRING,
        slo_kind STRING,
        deadline TIMESTAMP,
        predicted_at TIMESTAMP,
        remaining_s DOUBLE,
        slack_s DOUBLE,
        klass STRING,
        producer_job_id STRING,
        producer_state STRING,
        policy_version STRING,
        outcome STRING,
        outcome_at TIMESTAMP
    """,
    ("ops", "baseline_regimes"): """
        regime_id STRING NOT NULL,
        job_id STRING,
        effective_from_at TIMESTAMP,
        effective_from_sha STRING,
        origin STRING,
        decided_by STRING,
        identity_source STRING,
        reason STRING,
        incident_id STRING,
        created_at TIMESTAMP
    """,
    ("ops", "hypothesis_reviews"): """
        review_id STRING NOT NULL,
        hypothesis_id STRING,
        incident_id STRING,
        decision STRING,
        reviewer STRING,
        at TIMESTAMP,
        note STRING
    """,
    ("ops", "narratives"): """
        narrative_id STRING NOT NULL,
        incident_id STRING,
        source STRING,
        sentences_json STRING,
        model STRING,
        trace_id STRING,
        rejected_reason STRING,
        created_at TIMESTAMP
    """,
    ("ops", "run_cost"): """
        run_id STRING NOT NULL,
        incident_id STRING,
        status STRING,
        dbus DOUBLE,
        list_cost_usd DOUBLE,
        baseline_cost_usd DOUBLE,
        incremental_cost_usd DOUBLE,
        source_ref STRING,
        updated_at TIMESTAMP
    """,
    ("ops", "ticket_outbox"): """
        correlation_key STRING NOT NULL,
        incident_id STRING,
        status STRING,
        attempts INT,
        next_attempt_at TIMESTAMP,
        last_error STRING,
        issue_key STRING,
        issue_url STRING,
        summary STRING,
        description STRING,
        updated_at TIMESTAMP
    """,
    ("ops", "dlq"): """
        dlq_id STRING NOT NULL,
        source STRING,
        payload STRING,
        error STRING,
        at TIMESTAMP
    """,
    ("ops", "connector_checkpoints"): """
        connector STRING NOT NULL,
        cursor STRING,
        last_success_at TIMESTAMP,
        last_error STRING
    """,
    ("ops", "capabilities"): """
        capability STRING NOT NULL,
        status STRING,
        detail STRING,
        checked_at TIMESTAMP
    """,
    ("ops", "rule_results"): """
        result_id STRING NOT NULL,
        contract_id STRING,
        rule_id STRING,
        asset STRING,
        dimension STRING,
        status STRING,
        numerator BIGINT,
        denominator BIGINT,
        ratio DOUBLE,
        threshold STRING,
        severity STRING,
        window STRING,
        query_hash STRING,
        sample_json STRING,
        error_message STRING,
        evaluated_at TIMESTAMP
    """,
    ("ops", "contracts"): """
        contract_id STRING NOT NULL,
        version STRING,
        status STRING,
        owner STRING,
        producer STRING,
        asset STRING,
        classification STRING,
        declared_consumers ARRAY<STRING>,
        rule_count INT,
        loaded_at TIMESTAMP
    """,
}

# Migrações aditivas: renomear coluna exigiria column mapping e mudança de protocolo
# da tabela Delta. `subject` passa a ser a coluna canônica e `job_id` fica preenchida
# em paralelo enquanto houver leitor antigo.
MIGRATIONS = (
    ("ops", "incidents", "ADD COLUMN subject STRING"),
    ("ops", "incidents", "ADD COLUMN declared_consumers ARRAY<STRING>"),
    ("ops", "incidents", "ADD COLUMN impact_score DOUBLE"),
    ("ops", "incidents", "ADD COLUMN impact_policy_version STRING"),
    ("ops", "incidents", "ADD COLUMN escalated_from STRING"),
    ("ops", "incidents", "ADD COLUMN escalation_reason STRING"),
    ("ops", "incidents", "ADD COLUMN acknowledged_at TIMESTAMP"),
    ("ops", "incidents", "ADD COLUMN acknowledged_by STRING"),
    ("ops", "dlq", "ADD COLUMN error_class STRING"),
    ("ops", "dlq", "ADD COLUMN attempts INT"),
    ("ops", "dlq", "ADD COLUMN first_at TIMESTAMP"),
    ("ops", "dlq", "ADD COLUMN next_attempt_at TIMESTAMP"),
    ("ops", "dlq", "ADD COLUMN status STRING"),
)
BACKFILLS = (
    ("ops", "incidents", "UPDATE {table} SET subject = job_id WHERE subject IS NULL"),
)


def ensure_schemas(spark: Any, settings: Settings) -> None:
    for layer in SCHEMAS:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {settings.schema(layer)}")


def ensure_volume(spark: Any, settings: Settings) -> None:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {settings.schema('platform')}.landing")


# A trilha de auditoria recusa UPDATE e DELETE no próprio Delta; a cadeia de hash denuncia o
# resto (tabela recriada ou editada por fora).
TABLE_PROPERTIES: dict[tuple[str, str], str] = {
    ("ops", "audit_log"): "'delta.appendOnly' = 'true'",
}


def ensure_tables(spark: Any, settings: Settings) -> None:
    for (layer, name), columns in TABLES.items():
        propriedades = TABLE_PROPERTIES.get((layer, name))
        clausula = f" TBLPROPERTIES ({propriedades})" if propriedades else ""
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {settings.table(layer, name)} ({columns}) USING DELTA{clausula}"
        )
    for (layer, name), propriedades in TABLE_PROPERTIES.items():
        # Idempotente: garante a propriedade também em tabela criada antes dela existir.
        spark.sql(f"ALTER TABLE {settings.table(layer, name)} SET TBLPROPERTIES ({propriedades})")


def apply_migrations(spark: Any, settings: Settings) -> list[str]:
    """Migrações aditivas e idempotentes: o que já foi aplicado falha e é ignorado."""
    applied: list[str] = []
    for layer, table, clause in MIGRATIONS:
        try:
            spark.sql(f"ALTER TABLE {settings.table(layer, table)} {clause}")
            applied.append(f"{table}: {clause}")
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                logger.warning("migração %s em %s falhou: %s", clause, table, exc)
            else:
                logger.debug("migração já aplicada: %s", clause)

    for layer, table, statement in BACKFILLS:
        try:
            spark.sql(statement.format(table=settings.table(layer, table)))
            applied.append(f"{table}: backfill")
        except Exception as exc:
            logger.warning("backfill em %s falhou: %s", table, exc)
    return applied


def ensure_gold_view(spark: Any, settings: Settings) -> bool:
    source = settings.table("silver", "run_features")
    try:
        spark.sql(
            f"CREATE OR REPLACE VIEW {settings.table('gold', 'run_features')} "
            f"AS SELECT * FROM {source}"
        )
        return True
    except Exception as exc:
        logger.info("gold view not created yet (%s); run the pipeline first", exc)
        return False


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    ensure_schemas(spark, settings)
    ensure_volume(spark, settings)
    ensure_tables(spark, settings)
    for migration in apply_migrations(spark, settings):
        logger.info("migração aplicada: %s", migration)
    ensure_gold_view(spark, settings)
    logger.info("bootstrap complete for catalog %s", settings.catalog)


if __name__ == "__main__":
    main()
