"""Executa as etapas Python do ciclo numa única sessão.

Cada task de um job serverless paga a própria inicialização — eram seis partidas para
seis etapas que compartilham a mesma SparkSession. Aqui elas rodam em sequência, no
mesmo processo, e o pipeline Lakeflow continua como task separada porque tem runtime
próprio.

Uma etapa que falha não derruba as demais: o erro é registrado e o ciclo segue, porque
perder a correlação inteira por causa do Jira indisponível seria pior do que seguir sem
o ticket.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from eict.config import parse_settings

PIPELINE_POLL_SECONDS = 15
PIPELINE_TIMEOUT_SECONDS = 1800
PIPELINE_DONE = {"COMPLETED", "FAILED", "CANCELED"}

logger = logging.getLogger(__name__)

STAGE_FAILED = "falhou"
STAGE_OK = "ok"


@dataclass(frozen=True)
class StageResult:
    name: str
    status: str
    seconds: float
    error: str | None = None

    def __str__(self) -> str:
        detalhe = f" ({self.error})" if self.error else ""
        return f"{self.name}: {self.status} em {self.seconds:.1f}s{detalhe}"


def run_stage(name: str, action: Callable[[], None]) -> StageResult:
    started = time.monotonic()
    try:
        action()
        return StageResult(name, STAGE_OK, time.monotonic() - started)
    except Exception as exc:
        logger.exception("etapa %s falhou", name)
        return StageResult(name, STAGE_FAILED, time.monotonic() - started, str(exc)[:300])


def run_pipeline(pipeline_id: str) -> None:
    """Dispara o pipeline Lakeflow e espera terminar.

    Ter o pipeline como task separada obrigava a uma segunda task Python depois dele —
    e cada task paga ~4 min montando o ambiente. Chamando pelo SDK, o ciclo inteiro cabe
    num provisionamento só.
    """
    from databricks.sdk import WorkspaceClient

    if not pipeline_id:
        logger.info("sem pipeline_id: etapa do medallion ignorada")
        return

    client = WorkspaceClient()
    update = client.pipelines.start_update(pipeline_id=pipeline_id, full_refresh=False)
    deadline = time.monotonic() + PIPELINE_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        estado = client.pipelines.get_update(
            pipeline_id=pipeline_id, update_id=update.update_id
        ).update.state
        nome = getattr(estado, "value", str(estado))
        if nome in PIPELINE_DONE:
            if nome != "COMPLETED":
                raise RuntimeError(f"pipeline terminou em {nome}")
            return
        time.sleep(PIPELINE_POLL_SECONDS)

    raise TimeoutError(f"pipeline não terminou em {PIPELINE_TIMEOUT_SECONDS}s")


def cycle_stages(
    argv: list[str] | None, pipeline_id: str = ""
) -> list[tuple[str, Callable[[], None]]]:
    """O ciclo inteiro, na ordem em que as etapas dependem umas das outras."""
    from eict.jobs import bootstrap_ops, collect, correlate, dispatch, narrate, quality, semantics

    return [
        ("bootstrap", lambda: bootstrap_ops.main(argv)),
        ("collect", lambda: collect.main(argv)),
        ("medallion", lambda: run_pipeline(pipeline_id)),
        ("quality", lambda: quality.main(argv)),
        ("semantics", lambda: semantics.main(argv)),
        ("correlate", lambda: correlate.main(argv)),
        ("narrate", lambda: narrate.main(argv)),
        ("dispatch", lambda: dispatch.main(argv)),
    ]


def summarize(results: list[StageResult]) -> str:
    total = sum(result.seconds for result in results)
    falhas = [result for result in results if result.status == STAGE_FAILED]
    linhas = [f"  {result}" for result in results]
    cabecalho = (
        f"ciclo concluído em {total:.1f}s "
        f"({len(results) - len(falhas)}/{len(results)} etapas ok)"
    )
    return "\n".join([cabecalho, *linhas])


def run_all(etapas: list[tuple[str, Callable[[], None]]]) -> None:
    results = [run_stage(name, action) for name, action in etapas]
    print(summarize(results))

    falhas = [result for result in results if result.status == STAGE_FAILED]
    if falhas:
        raise SystemExit(f"{len(falhas)} etapa(s) falharam: {', '.join(f.name for f in falhas)}")


def pipeline_id_from(argv: list[str] | None) -> str:
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--pipeline-id", default="")
    known, _ = parser.parse_known_args(argv)
    return known.pipeline_id


def main(argv: list[str] | None = None) -> None:
    """Ciclo inteiro num processo: uma task, um provisionamento de ambiente."""
    import sys

    argv = argv if argv is not None else sys.argv[1:]
    parse_settings(argv)
    run_all(cycle_stages(argv, pipeline_id_from(argv)))


if __name__ == "__main__":
    main()
