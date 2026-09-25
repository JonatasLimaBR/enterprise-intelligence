from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from eict.domain.models import SUCCESS_STATE, Run

MONITOR_TAG = "eict_monitor"
TERMINAL_LIFE_CYCLE_STATES = {"TERMINATED", "INTERNAL_ERROR", "SKIPPED"}


@dataclass(frozen=True)
class MonitoredJob:
    job_id: str
    name: str
    env_hash: str


def list_monitored_jobs(client: Any, tag: str = MONITOR_TAG) -> list[MonitoredJob]:
    jobs: list[MonitoredJob] = []
    for job in client.jobs.list(expand_tasks=True):
        settings = job.settings
        tags = getattr(settings, "tags", None) or {}
        if tags.get(tag) != "true":
            continue
        jobs.append(
            MonitoredJob(
                job_id=str(job.job_id),
                name=getattr(settings, "name", "") or "",
                env_hash=environment_hash(settings),
            )
        )
    return jobs


def active_run(client: Any, job: MonitoredJob) -> tuple[str, datetime] | None:
    """Run em andamento mais recente do job: (run_id, início), ou `None` se parado.

    O `collect` só lista runs concluídos; sem isto, um produtor já entregando apareceria como
    parado e o risco de SLA alarmaria justamente quem está cumprindo o prazo.
    """
    for base_run in client.jobs.list_runs(job_id=int(job.job_id), active_only=True, limit=1):
        start_ms = getattr(base_run, "start_time", None)
        if start_ms:
            return str(base_run.run_id), _to_datetime(start_ms)
    return None


def run_results(client: Any, job_ids: list[str], since_ms: int) -> dict[str, bool]:
    """Sucesso de cada run concluído desde `since_ms`, para jobs fora de `run_features`.

    O próprio ciclo EICT não é monitorado; sem isto, o custo por ciclo não saberia quais runs
    deram certo.
    """
    resultados: dict[str, bool] = {}
    for job_id in job_ids:
        for base_run in client.jobs.list_runs(job_id=int(job_id), completed_only=True, start_time_from=since_ms):
            estado = _enum_value(getattr(getattr(base_run, "state", None), "result_state", None))
            resultados[str(base_run.run_id)] = estado == SUCCESS_STATE
    return resultados


def environment_hash(settings: Any) -> str:
    environments = getattr(settings, "environments", None) or []
    spec = [
        {
            "environment_key": getattr(item, "environment_key", None),
            "spec": _as_dict(getattr(item, "spec", None)),
        }
        for item in environments
    ]
    payload = {
        "environments": spec,
        "performance_target": _enum_value(getattr(settings, "performance_target", None)),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f"env-{digest[:12]}"


def list_completed_runs(
    client: Any, job: MonitoredJob, since_ms: int | None = None
) -> list[Run]:
    runs: list[Run] = []
    for base_run in client.jobs.list_runs(
        job_id=int(job.job_id),
        completed_only=True,
        start_time_from=since_ms,
        expand_tasks=True,
    ):
        run = to_domain_run(base_run, job)
        if run is not None:
            runs.append(run)
    return sorted(runs, key=lambda item: item.end_time)


def to_domain_run(base_run: Any, job: MonitoredJob) -> Run | None:
    start_ms = getattr(base_run, "start_time", None)
    end_ms = getattr(base_run, "end_time", None)
    if not start_ms or not end_ms:
        return None
    state = getattr(base_run, "state", None)
    life_cycle = _enum_value(getattr(state, "life_cycle_state", None))
    if life_cycle not in TERMINAL_LIFE_CYCLE_STATES:
        return None
    parameters = job_parameters(base_run)
    setup_s, execution_s, _ = run_timing(base_run)
    return Run(
        run_id=str(base_run.run_id),
        job_id=job.job_id,
        start_time=_to_datetime(start_ms),
        end_time=_to_datetime(end_ms),
        duration_s=(end_ms - start_ms) / 1000,
        result_state=_enum_value(getattr(state, "result_state", None)) or "UNKNOWN",
        git_sha=parameters.get("git_sha"),
        env_hash=job.env_hash,
        input_rows=None,
        job_parameters=parameters,
        setup_s=setup_s,
        execution_s=execution_s,
    )


def run_timing(base_run: Any) -> tuple[float | None, float | None, int]:
    """Setup e execução somados das tasks, em segundos, e o número de tasks.

    No nível do run, `execution_duration` vem 0 em jobs de formato multi-task (todos os
    atuais): o tempo real está nas tasks. Timing parcial não é medido — uma task sem o campo
    faria a soma parecer mais rápida do que foi.
    """
    tasks = getattr(base_run, "tasks", None) or []
    execucoes = [getattr(task, "execution_duration", None) for task in tasks]
    setups = [getattr(task, "setup_duration", None) for task in tasks]
    if not tasks or any(valor is None for valor in execucoes):
        return None, None, len(tasks)
    setup_total = sum(valor or 0 for valor in setups) / 1000
    return setup_total, sum(execucoes) / 1000, len(tasks)


def job_parameters(base_run: Any) -> dict[str, str]:
    parameters: dict[str, str] = {}
    for parameter in getattr(base_run, "job_parameters", None) or []:
        name = getattr(parameter, "name", None)
        if not name:
            continue
        value = getattr(parameter, "value", None)
        if value is None:
            value = getattr(parameter, "default", None)
        if value is not None:
            parameters[name] = str(value)
    return parameters


def _to_datetime(epoch_ms: int) -> datetime:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=UTC)


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _as_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "as_dict"):
        return value.as_dict()
    return {"repr": str(value)}
