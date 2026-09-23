"""Lê o grafo de lineage do Databricks e o mantém acumulado em `ops.lineage_graph`.

A tabela guarda a impressão digital de schema **atual e anterior**. Guardar só a atual
tornaria a mudança invisível: o `MERGE` usa `UPDATE SET *` e sobrescreveria o valor
antes de qualquer leitura seguinte. A comparação mora dentro de `merge_graph`, e não
na ordem em que o chamador resolve invocar as coisas.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from eict.adapters import capabilities as capability_probe
from eict.adapters import store
from eict.config import Settings
from eict.domain.impact import Edge
from eict.domain.models import content_hash

logger = logging.getLogger(__name__)

LINEAGE_WINDOW_DAYS = 30
GRAPH_TABLE = "lineage_graph"


def fetch_edges(spark: Any, settings: Settings, available: bool) -> tuple[Edge, ...]:
    """Observações do ciclo. Sem a capability, tupla vazia — nunca exceção."""
    if not available:
        logger.info("lineage indisponível: grafo não atualizado neste ciclo")
        return ()
    prefixo = f"{settings.catalog}.{settings.schema_prefix}"
    try:
        records = store.query(
            spark,
            f"""
            SELECT source_table_full_name AS source,
                   coalesce(target_table_full_name, '') AS target,
                   coalesce(entity_type, '') AS entity_type,
                   coalesce(entity_id, '') AS entity_id,
                   max(event_time) AS last_seen
            FROM {capability_probe.TABLE_LINEAGE}
            WHERE event_time > current_timestamp() - INTERVAL {LINEAGE_WINDOW_DAYS} DAYS
              AND source_table_full_name IS NOT NULL
              AND source_table_full_name LIKE '{prefixo}%'
            GROUP BY 1, 2, 3, 4
            """,
        )
    except Exception as exc:
        logger.warning("consulta de lineage falhou: %s", exc)
        return ()
    return tuple(
        Edge(
            source=record["source"],
            target=record["target"] or "",
            entity_type=record["entity_type"] or "",
            entity_id=record["entity_id"] or "",
            last_seen=store.ensure_utc(record["last_seen"]),
        )
        for record in records
        if record.get("source")
    )


def schema_fingerprints(spark: Any, settings: Settings) -> dict[str, str]:
    """Hash de `coluna:tipo` ordenado por tabela — funciona com ou sem contrato."""
    try:
        records = store.query(
            spark,
            f"""
            SELECT table_catalog, table_schema, table_name, column_name, data_type
            FROM {settings.catalog}.information_schema.columns
            WHERE table_schema LIKE '{settings.schema_prefix}%'
            ORDER BY table_catalog, table_schema, table_name, ordinal_position
            """,
        )
    except Exception as exc:
        logger.warning("leitura de schema falhou: %s", exc)
        return {}
    colunas: dict[str, list[str]] = {}
    for record in records:
        ativo = (
            f"{record['table_catalog']}.{record['table_schema']}.{record['table_name']}"
        )
        colunas.setdefault(ativo, []).append(f"{record['column_name']}:{record['data_type']}")
    return {ativo: content_hash(",".join(sorted(itens))) for ativo, itens in colunas.items()}


def merge_graph(
    spark: Any,
    settings: Settings,
    observations: tuple[Edge, ...],
    fingerprints: dict[str, str],
    now: datetime,
) -> int:
    """Acumula o grafo preservando `first_seen` e a impressão digital anterior."""
    if not observations:
        return 0
    anteriores = _existing_rows(spark, settings)
    linhas = [
        _graph_row(edge, anteriores.get(edge.edge_id, {}), fingerprints.get(edge.source, ""), now)
        for edge in observations
    ]
    return store.merge_rows(spark, settings.table("ops", GRAPH_TABLE), linhas, ["edge_id"])


def load_graph(spark: Any, settings: Settings) -> tuple[Edge, ...]:
    """O grafo acumulado, não só o que este ciclo viu."""
    try:
        records = store.query(
            spark,
            f"""
            SELECT source_asset, target_asset, entity_type, entity_id, last_seen
            FROM {settings.table('ops', GRAPH_TABLE)}
            """,
        )
    except Exception as exc:
        logger.warning("leitura do grafo falhou: %s", exc)
        return ()
    return tuple(
        Edge(
            source=record["source_asset"],
            target=record["target_asset"] or "",
            entity_type=record["entity_type"] or "",
            entity_id=record["entity_id"] or "",
            last_seen=store.ensure_utc(record["last_seen"]),
        )
        for record in records
        if record.get("source_asset")
    )


def changed_assets(spark: Any, settings: Settings) -> frozenset[str]:
    """Ativos cuja impressão digital mudou desde a observação anterior."""
    try:
        records = store.query(
            spark,
            f"""
            SELECT DISTINCT source_asset
            FROM {settings.table('ops', GRAPH_TABLE)}
            WHERE previous_fingerprint IS NOT NULL
              AND previous_fingerprint <> ''
              AND previous_fingerprint <> schema_fingerprint
            """,
        )
    except Exception as exc:
        logger.warning("leitura de mudanças de schema falhou: %s", exc)
        return frozenset()
    return frozenset(record["source_asset"] for record in records if record.get("source_asset"))


def _existing_rows(spark: Any, settings: Settings) -> dict[str, dict]:
    try:
        records = store.query(
            spark,
            f"""
            SELECT edge_id, schema_fingerprint, previous_fingerprint,
                   fingerprint_changed_at, first_seen, observed_cycles
            FROM {settings.table('ops', GRAPH_TABLE)}
            """,
        )
    except Exception as exc:
        logger.warning("leitura do grafo anterior falhou: %s", exc)
        return {}
    return {record["edge_id"]: record for record in records if record.get("edge_id")}


def _graph_row(edge: Edge, previous: dict, fingerprint: str, now: datetime) -> dict:
    guardada = previous.get("schema_fingerprint") or ""
    mudou = bool(guardada) and bool(fingerprint) and guardada != fingerprint
    return {
        "edge_id": edge.edge_id,
        "source_asset": edge.source,
        "target_asset": edge.target,
        "entity_type": edge.entity_type,
        "entity_id": edge.entity_id,
        "first_seen": previous.get("first_seen") or edge.last_seen,
        "last_seen": edge.last_seen,
        "schema_fingerprint": fingerprint or guardada,
        "previous_fingerprint": guardada if mudou else (previous.get("previous_fingerprint") or ""),
        "fingerprint_changed_at": now if mudou else previous.get("fingerprint_changed_at"),
        "observed_cycles": int(previous.get("observed_cycles") or 0) + 1,
    }
