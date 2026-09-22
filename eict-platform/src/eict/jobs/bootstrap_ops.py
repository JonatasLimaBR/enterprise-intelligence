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
        version INT
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
)
BACKFILLS = (
    ("ops", "incidents", "UPDATE {table} SET subject = job_id WHERE subject IS NULL"),
)


def ensure_schemas(spark: Any, settings: Settings) -> None:
    for layer in SCHEMAS:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {settings.schema(layer)}")


def ensure_volume(spark: Any, settings: Settings) -> None:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {settings.schema('platform')}.landing")


def ensure_tables(spark: Any, settings: Settings) -> None:
    for (layer, name), columns in TABLES.items():
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {settings.table(layer, name)} ({columns}) USING DELTA"
        )


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
