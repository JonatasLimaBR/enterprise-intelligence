"""Etapa do ciclo: lê o código do produtor, extrai as métricas e grava o que achou.

Roda entre `quality` e `correlate`: a comparação precisa existir antes do correlator, que a
transforma em incidente. Uma falha aqui não derruba o ciclo — `run_stage` isola a etapa.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eict.adapters import lineage, metric_loader, store
from eict.adapters.github import GitHubClient, GitHubError
from eict.config import Settings, parse_settings
from eict.domain import ontology
from eict.domain.extraction import extract
from eict.domain.metrics import compare

logger = logging.getLogger(__name__)


METRICS_DIRNAME = "metrics"


def metrics_dir(settings: Settings) -> Path:
    """Como os contratos, o registry viaja com o bundle, na raiz do projeto da plataforma.

    Um caminho relativo dependeria do diretório de trabalho do job, que não é o do bundle.
    """
    if settings.metrics_dir:
        return Path(settings.metrics_dir)
    return Path(__file__).resolve().parents[3] / METRICS_DIRNAME


def observed_metrics(
    client: GitHubClient | None, sources: tuple[tuple[str, str], ...], ref: str = ""
) -> list:
    """Extrai de cada arquivo declarado. Arquivo ausente é registrado, não inventado."""
    if client is None:
        logger.info("sem repositório do workload: extração de métricas ignorada")
        return []
    saida: list = []
    for path, asset in sources:
        try:
            source = client.fetch_file(path, ref)
        except GitHubError as exc:
            logger.warning("não foi possível ler %s: %s", path, exc)
            continue
        if not source:
            logger.warning("arquivo do registry não encontrado no repositório: %s", path)
            continue
        saida.extend(extract(source, path, asset))
    return saida


def persist(spark: Any, settings: Settings, observed: list, edges: tuple, now: datetime) -> None:
    if observed:
        store.merge_rows(
            spark,
            settings.table("ops", "metrics"),
            [store.metric_row(item, "", now) for item in observed],
            ["observation_id"],
        )
    if edges:
        store.merge_rows(
            spark,
            settings.table("ops", "ontology_edges"),
            [store.ontology_row(edge) for edge in edges],
            ["edge_id"],
        )


def build_ontology(spark: Any, settings: Settings, declarations: list, now: datetime) -> tuple:
    from eict.adapters.contract_loader import load_directory
    from eict.jobs.quality import contracts_dir

    contracts = list(load_directory(contracts_dir(settings)).active)
    return ontology.merge(
        ontology.from_lineage(list(lineage.load_graph(spark, settings)), now),
        ontology.from_contracts(contracts, now),
        ontology.from_metrics(declarations, now),
    )


def _client(settings: Settings) -> GitHubClient | None:
    """Mesmo token do `collect`, quando existir; repositório público funciona sem ele."""
    repo = settings.workload_repo or settings.github_repo
    if not repo:
        return None
    try:
        from databricks.sdk import WorkspaceClient

        token = WorkspaceClient().dbutils.secrets.get(settings.secret_scope, "github_token")
    except Exception as exc:
        logger.info("token do github indisponível (%s); acesso sem autenticação", exc)
        token = ""
    return GitHubClient(repo=repo, token=token)


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(UTC)

    registry = metric_loader.load_registry(metrics_dir(settings))
    for erro in registry.errors:
        logger.warning("registry de métricas: %s", erro)

    client = _client(settings)
    observed = observed_metrics(client, registry.sources)
    divergences = compare(list(registry.declarations), observed)

    persist(spark, settings, observed, build_ontology(spark, settings, list(registry.declarations), now), now)
    logger.info(
        "semantics: %d métricas observadas, %d divergências",
        len(observed),
        len(divergences),
    )


if __name__ == "__main__":
    main()
