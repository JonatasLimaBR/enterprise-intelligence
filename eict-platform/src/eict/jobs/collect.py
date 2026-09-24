from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from eict.adapters import capabilities as capability_probe
from eict.adapters import databricks_jobs, store
from eict.adapters.github import GitHubClient, GitHubError
from eict.config import Settings, parse_settings
from eict.domain import connectors
from eict.domain.envelope import Envelope
from eict.domain.models import Run

logger = logging.getLogger(__name__)

JOBS_CONNECTOR = "databricks_jobs"
GITHUB_CONNECTOR = "github"


def run_envelope(run: Run, settings: Settings, source: str, job_name: str = "") -> Envelope:
    return Envelope.create(
        source=source,
        type="execution.completed",
        subject=f"job/{run.job_id}/run/{run.run_id}",
        time=run.end_time,
        tenant_id=settings.tenant_id,
        data={
            "run_id": run.run_id,
            "job_id": run.job_id,
            "job_name": job_name,
            "start_time": run.start_time.isoformat(),
            "end_time": run.end_time.isoformat(),
            "duration_s": run.duration_s,
            "result_state": run.result_state,
            "git_sha": run.git_sha,
            "env_hash": run.env_hash,
            "job_parameters": run.job_parameters,
        },
    )


def timing_envelope(run: Run, settings: Settings, source: str) -> Envelope | None:
    """Setup e execução do run, num evento próprio.

    Não é campo de `execution.completed` porque o id do envelope ignora o payload: reemitir
    aquele evento com os campos novos geraria o mesmo id e o bronze o descartaria em silêncio.
    Evento próprio torna o backfill idempotente — o mesmo run gera sempre o mesmo id.
    """
    if run.execution_s is None:
        return None
    return Envelope.create(
        source=source,
        type="execution.timing",
        subject=f"job/{run.job_id}/run/{run.run_id}",
        time=run.end_time,
        tenant_id=settings.tenant_id,
        data={
            "run_id": run.run_id,
            "job_id": run.job_id,
            "setup_s": run.setup_s,
            "execution_s": run.execution_s,
        },
    )


def change_envelope(change, settings: Settings, source: str) -> Envelope:
    return Envelope.create(
        source=source,
        type="change.committed",
        subject=f"commit/{change.sha}",
        time=change.committed_at,
        tenant_id=settings.tenant_id,
        data={
            "sha": change.sha,
            "repo": change.repo,
            "author": change.author,
            "message": change.message,
            "files": list(change.files),
            "patch": change.patch,
        },
    )


def referenced_shas(spark: Any, settings: Settings) -> set[str]:
    records = store.query(
        spark,
        f"SELECT DISTINCT git_sha FROM {settings.table('silver', 'runs')} "
        "WHERE git_sha IS NOT NULL",
    )
    return {record["git_sha"] for record in records if record.get("git_sha")}


def known_shas(spark: Any, settings: Settings) -> set[str]:
    records = store.query(
        spark,
        f"SELECT subject FROM {settings.table('bronze', 'observations')} "
        "WHERE type = 'change.committed'",
    )
    return {record["subject"].split("/", 1)[1] for record in records if "/" in record["subject"]}


def read_cursor(spark: Any, settings: Settings, connector: str) -> int | None:
    records = store.query(
        spark,
        f"SELECT cursor FROM {settings.table('ops', 'connector_checkpoints')} "
        f"WHERE connector = '{connector}'",
    )
    if not records or not records[0]["cursor"]:
        return None
    return int(records[0]["cursor"])


def collect_runs(spark: Any, workspace: Any, settings: Settings, source: str) -> list[Envelope]:
    cursor = read_cursor(spark, settings, JOBS_CONNECTOR)
    envelopes: list[Envelope] = []
    latest = cursor or 0
    for job in databricks_jobs.list_monitored_jobs(workspace):
        for run in databricks_jobs.list_completed_runs(workspace, job, since_ms=cursor):
            envelopes.append(run_envelope(run, settings, source, job.name))
            timing = timing_envelope(run, settings, source)
            if timing is not None:
                envelopes.append(timing)
            latest = max(latest, int(run.end_time.timestamp() * 1000))
    if latest:
        store.merge_rows(
            spark,
            settings.table("ops", "connector_checkpoints"),
            [store.checkpoint_row(JOBS_CONNECTOR, str(latest + 1), _now())],
            ["connector"],
        )
    return envelopes


def collect_monitored_jobs(spark: Any, workspace: Any, settings: Settings) -> int:
    """Registro dos jobs monitorados, com o run em andamento de cada um.

    É daqui que o produtor de um contrato é resolvido por nome exato — e não por substring do
    `job_name` dos runs, nulo nos runs antigos.
    """
    agora = _now()
    linhas = []
    for job in databricks_jobs.list_monitored_jobs(workspace):
        try:
            ativo = databricks_jobs.active_run(workspace, job)
        except Exception as exc:
            logger.warning("runs ativos de %s indisponíveis: %s", job.name, exc)
            ativo = None
        linhas.append(store.monitored_job_row(job, ativo, agora))
    if linhas:
        store.merge_rows(spark, settings.table("ops", "monitored_jobs"), linhas, ["job_id"])
    return len(linhas)


def backfill_timings(workspace: Any, settings: Settings, source: str) -> list[Envelope]:
    """Timing de toda a história dos jobs monitorados, sem tocar no cursor do `collect`."""
    envelopes: list[Envelope] = []
    for job in databricks_jobs.list_monitored_jobs(workspace):
        for run in databricks_jobs.list_completed_runs(workspace, job, since_ms=None):
            timing = timing_envelope(run, settings, source)
            if timing is not None:
                envelopes.append(timing)
    return envelopes


def load_dlq(spark: Any, settings: Settings, source: str) -> dict:
    records = store.query(
        spark, f"SELECT * FROM {settings.table('ops', 'dlq')} WHERE source = '{source}'"
    )
    return {entry.dlq_id: entry for entry in store.to_dlq_entries(records)}


def fetch_changes(
    github: GitHubClient, pending: list[str], dlq: dict, settings: Settings, source: str, now: datetime
) -> tuple[list[Envelope], list, str | None, int]:
    """Busca os commits devidos. Devolve envelopes, entradas da DLQ a gravar, último erro e sucessos.

    Quarentena não se tenta; retentativa só depois do `next_attempt_at`. Um commit que não
    existe (422) vai para a quarentena na primeira falha em vez de ser buscado a cada ciclo.
    """
    envelopes: list[Envelope] = []
    alteradas = []
    ultimo_erro: str | None = None
    sucessos = 0
    for sha in pending:
        dlq_id = f"github-{sha}"
        existente = dlq.get(dlq_id)
        if not connectors.should_try(existente, now):
            continue
        try:
            envelopes.append(change_envelope(github.commit(sha), settings, source))
            sucessos += 1
            if existente is not None and existente.is_open:
                alteradas.append(connectors.record_success(existente, now))
        except GitHubError as exc:
            ultimo_erro = str(exc)[:500]
            alteradas.append(
                connectors.record_failure(
                    existente, dlq_id, GITHUB_CONNECTOR, sha, ultimo_erro, exc.status, now
                )
            )
    return envelopes, alteradas, ultimo_erro, sucessos


def collect_changes(
    spark: Any, settings: Settings, github: GitHubClient | None, shas: set[str], source: str
) -> list[Envelope]:
    if github is None or not shas:
        return []
    agora = _now()
    pendentes = sorted(shas - known_shas(spark, settings))
    envelopes, alteradas, erro, sucessos = fetch_changes(
        github, pendentes, load_dlq(spark, settings, GITHUB_CONNECTOR), settings, source, agora
    )
    if alteradas:
        store.merge_rows(
            spark, settings.table("ops", "dlq"), [store.dlq_row(item) for item in alteradas], ["dlq_id"]
        )
    if sucessos or erro:
        record_checkpoint(spark, settings, GITHUB_CONNECTOR, agora if sucessos else None, erro)
    return envelopes


def record_health(spark: Any, settings: Settings, now: datetime) -> list:
    """Saúde de cada conector, calculada aqui porque o console não importa o domínio."""
    checkpoints = {
        record["connector"]: record
        for record in store.query(spark, f"SELECT * FROM {settings.table('ops', 'connector_checkpoints')}")
    }
    saude = []
    for connector in (JOBS_CONNECTOR, GITHUB_CONNECTOR):
        checkpoint = checkpoints.get(connector, {})
        saude.append(
            connectors.health(
                connector,
                checkpoint.get("last_success_at"),
                checkpoint.get("last_error"),
                list(load_dlq(spark, settings, connector).values()),
                now,
            )
        )
    store.merge_rows(
        spark,
        settings.table("ops", "connector_health"),
        [
            {
                "connector": item.connector,
                "status": item.status,
                "retrying": item.retrying,
                "quarantined": item.quarantined,
                "last_success_at": item.last_success_at,
                "last_error": item.last_error or None,
                "detail": item.detail,
                "evaluated_at": now,
            }
            for item in saude
        ],
        ["connector"],
    )
    return saude


def record_checkpoint(
    spark: Any, settings: Settings, connector: str, success_at: datetime | None, error: str | None
) -> None:
    """Preserva o último sucesso: um ciclo só com falhas não pode apagá-lo."""
    anterior = store.query(
        spark,
        f"SELECT * FROM {settings.table('ops', 'connector_checkpoints')} WHERE connector = '{connector}'",
    )
    ultimo = anterior[0] if anterior else {}
    store.merge_rows(
        spark,
        settings.table("ops", "connector_checkpoints"),
        [
            {
                "connector": connector,
                "cursor": ultimo.get("cursor"),
                "last_success_at": success_at or ultimo.get("last_success_at"),
                "last_error": error if success_at is None else None,
            }
        ],
        ["connector"],
    )


def persist(spark: Any, settings: Settings, envelopes: list[Envelope]) -> int:
    if not envelopes:
        return 0
    rows = [envelope.as_row() for envelope in envelopes]
    return store.insert_missing(
        spark, settings.table("bronze", "observations"), rows, "id"
    )


def main(argv: list[str] | None = None) -> None:
    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    workspace = WorkspaceClient()
    source = f"databricks/{workspace.config.host}"

    run_envelopes = collect_runs(spark, workspace, settings, source)
    collect_monitored_jobs(spark, workspace, settings)
    shas = {
        envelope.data["git_sha"]
        for envelope in run_envelopes
        if envelope.data.get("git_sha")
    } | referenced_shas(spark, settings)
    github = _github_client(workspace, settings)
    change_envelopes = collect_changes(spark, settings, github, shas, source)

    persisted = persist(spark, settings, run_envelopes + change_envelopes)
    for item in record_health(spark, settings, _now()):
        logger.info("conector %s: %s (%s)", item.connector, item.status, item.detail)

    store.merge_rows(
        spark,
        settings.table("ops", "capabilities"),
        [
            {
                "capability": capability.capability,
                "status": capability.status,
                "detail": capability.detail,
                "checked_at": capability.checked_at,
            }
            for capability in capability_probe.discover(spark, settings.landing_dir)
        ],
        ["capability"],
    )
    logger.info("collected %s observations", persisted)


def _github_client(workspace: Any, settings: Settings) -> GitHubClient | None:
    if not settings.github_repo:
        return None
    try:
        token = workspace.dbutils.secrets.get(settings.secret_scope, "github_token")
    except Exception as exc:
        logger.info("github token unavailable (%s); using unauthenticated access", exc)
        token = ""
    return GitHubClient(repo=settings.github_repo, token=token)


def _now() -> datetime:
    return datetime.now(UTC)


if __name__ == "__main__":
    main()
