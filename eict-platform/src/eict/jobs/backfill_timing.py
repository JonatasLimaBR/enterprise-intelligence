"""Backfill único do tempo de execução dos runs já coletados.

Avulso, não etapa do ciclo: a listagem completa da história custaria a cada cinco minutos.
Rodar de novo não muda nada — o mesmo run gera o mesmo id de `execution.timing`, e o bronze
grava só o que falta.
"""

from __future__ import annotations

import logging

from eict.config import parse_settings
from eict.jobs.collect import backfill_timings, persist

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    workspace = WorkspaceClient()
    source = f"databricks/{workspace.config.host}"

    envelopes = backfill_timings(workspace, settings, source)
    gravados = persist(spark, settings, envelopes)
    print(f"backfill de timing: {len(envelopes)} runs com tempo medido, {gravados} inseridos no bronze")


if __name__ == "__main__":
    main()
