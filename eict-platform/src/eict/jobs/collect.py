from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from eict.adapters import capabilities as capability_probe
from eict.adapters import databricks_jobs, store
from eict.adapters.github import GitHubClient, GitHubError
from eict.config import Settings, parse_settings
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


def collect_changes(
    spark: Any, settings: Settings, github: GitHubClient | None, shas: set[str], source: str
) -> list[Envelope]:
    if github is None or not shas:
        return []
    already = known_shas(spark, settings)
    envelopes: list[Envelope] = []
    for sha in sorted(shas - already):
        try:
            envelopes.append(change_envelope(github.commit(sha), settings, source))
        except GitHubError as exc:
            store.append_rows(
                spark,
                settings.table("ops", "dlq"),
                [
                    {
                        "dlq_id": f"github-{sha}",
                        "source": GITHUB_CONNECTOR,
                        "payload": sha,
                        "error": str(exc)[:500],
                        "at": _now(),
                    }
                ],
            )
    return envelopes


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
