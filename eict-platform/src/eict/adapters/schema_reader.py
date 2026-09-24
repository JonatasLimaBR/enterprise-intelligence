from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SchemaUnavailableError(RuntimeError):
    """O catálogo não respondeu sobre a tabela: é erro de execução, não violação."""


def table_columns(spark: Any, asset: str) -> dict[str, str]:
    """Colunas atuais da tabela, pelo catálogo, no formato {nome: tipo}."""
    catalog, schema, table = _split(asset)
    try:
        rows = spark.sql(
            f"""
            SELECT column_name, full_data_type
            FROM {catalog}.information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{table}'
            """
        ).collect()
    except Exception as exc:
        raise SchemaUnavailableError(f"{asset}: {exc}") from exc

    if not rows:
        raise SchemaUnavailableError(f"{asset}: tabela não encontrada no catálogo")
    return {row["column_name"]: row["full_data_type"] for row in rows}


def write_times(spark: Any, asset: str, since: Any) -> list:
    """Instantes das escritas desde `since`, pelo histórico Delta.

    O prazo diário e o desfecho de uma previsão perguntam "houve escrita neste intervalo?" — a
    última escrita sozinha não responde quando houve mais de uma.
    """
    limite = since.isoformat(sep=" ", timespec="seconds")
    try:
        rows = spark.sql(
            f"""
            SELECT timestamp FROM (DESCRIBE HISTORY {asset})
            WHERE operation NOT IN ('OPTIMIZE', 'VACUUM START', 'VACUUM END')
              AND timestamp >= TIMESTAMP '{limite}'
            """
        ).collect()
    except Exception as exc:
        raise SchemaUnavailableError(f"{asset}: {exc}") from exc
    return sorted(row["timestamp"] for row in rows)


def last_write_delay_seconds(spark: Any, asset: str) -> tuple[Any, int]:
    """Última escrita e atraso em segundos, a partir do histórico Delta."""
    try:
        row = spark.sql(
            f"""
            SELECT max(timestamp) AS ultima_escrita,
                   unix_timestamp(current_timestamp()) - unix_timestamp(max(timestamp)) AS atraso_s
            FROM (DESCRIBE HISTORY {asset})
            """
        ).first()
    except Exception as exc:
        raise SchemaUnavailableError(f"{asset}: {exc}") from exc

    if row is None or row["ultima_escrita"] is None:
        raise SchemaUnavailableError(f"{asset}: sem histórico Delta")
    return row["ultima_escrita"], int(row["atraso_s"])


def recent_row_counts(spark: Any, results_table: str, rule_id: str, limit: int = 10) -> list[int]:
    """Contagens recentes registradas pela própria regra de volume."""
    try:
        rows = spark.sql(
            f"""
            SELECT numerator FROM {results_table}
            WHERE rule_id = '{rule_id}' AND status <> 'evaluation_error'
            ORDER BY evaluated_at DESC LIMIT {limit}
            """
        ).collect()
    except Exception as exc:
        logger.info("histórico de volume indisponível para %s: %s", rule_id, exc)
        return []
    return [int(row["numerator"]) for row in rows if row["numerator"] is not None]


def _split(asset: str) -> tuple[str, str, str]:
    parts = asset.split(".")
    if len(parts) != 3:
        raise SchemaUnavailableError(f"nome qualificado inválido: {asset}")
    return parts[0], parts[1], parts[2]
