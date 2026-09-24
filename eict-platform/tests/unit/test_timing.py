"""Tempo de execução: coletado das tasks, emitido como evento próprio, idempotente."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from eict.adapters.databricks_jobs import MonitoredJob, run_timing, to_domain_run
from eict.config import Settings
from eict.jobs.collect import backfill_timings, run_envelope, timing_envelope
from tests.conftest import make_run

SETTINGS = Settings()
SOURCE = "databricks/teste"


def _task(setup_ms, exec_ms):
    return SimpleNamespace(setup_duration=setup_ms, execution_duration=exec_ms)


def _base_run(run_id=418191947092239, tasks=None, start=1_000_000, end=1_570_000):
    return SimpleNamespace(
        run_id=run_id,
        start_time=start,
        end_time=end,
        state=SimpleNamespace(life_cycle_state="TERMINATED", result_state="SUCCESS"),
        job_parameters=[],
        tasks=tasks if tasks is not None else [_task(134_000, 1_435_000)],
    )


def test_at18_task_unica_vira_setup_e_execucao():
    assert run_timing(_base_run()) == (134.0, 1435.0, 1)


def test_varias_tasks_somam():
    assert run_timing(_base_run(tasks=[_task(10_000, 20_000), _task(5_000, 7_000)])) == (15.0, 27.0, 2)


def test_task_sem_execucao_nao_e_medida():
    """Timing parcial faria o run parecer mais rápido do que foi."""
    assert run_timing(_base_run(tasks=[_task(10_000, 20_000), _task(5_000, None)])) == (None, None, 2)


def test_run_sem_tasks_nao_e_medido():
    assert run_timing(_base_run(tasks=[])) == (None, None, 0)


def test_run_de_dominio_carrega_o_timing():
    job = MonitoredJob(job_id="580618456320695", name="sales_daily", env_hash="env")

    run = to_domain_run(_base_run(), job)

    assert run.execution_s == 1435.0
    assert run.setup_s == 134.0
    assert run.duration_s == 570.0


def test_at16_mesmo_run_gera_o_mesmo_id_de_timing():
    run = replace(make_run(6, 1570), setup_s=134.0, execution_s=1435.0)

    assert timing_envelope(run, SETTINGS, SOURCE).id == timing_envelope(run, SETTINGS, SOURCE).id


def test_timing_nao_colide_com_execution_completed():
    """Mesmo subject e instante, tipo diferente: ids diferentes — o bronze grava os dois."""
    run = replace(make_run(6, 1570), setup_s=134.0, execution_s=1435.0)

    assert timing_envelope(run, SETTINGS, SOURCE).id != run_envelope(run, SETTINGS, SOURCE).id


def test_run_sem_execucao_nao_emite_timing():
    assert timing_envelope(make_run(6, 1570), SETTINGS, SOURCE) is None


def test_payload_do_timing():
    run = replace(make_run(6, 1570), setup_s=134.0, execution_s=1435.0)

    envelope = timing_envelope(run, SETTINGS, SOURCE)

    assert envelope.type == "execution.timing"
    assert envelope.data == {
        "run_id": run.run_id,
        "job_id": run.job_id,
        "setup_s": 134.0,
        "execution_s": 1435.0,
    }


class _Jobs:
    def __init__(self, runs):
        self.runs = runs
        self.chamadas = []

    def list_runs(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.runs


def test_at17_backfill_percorre_a_historia_inteira_e_e_idempotente(monkeypatch):
    from eict.adapters import databricks_jobs

    job = MonitoredJob(job_id="580618456320695", name="sales_daily", env_hash="env")
    monkeypatch.setattr(databricks_jobs, "list_monitored_jobs", lambda workspace: [job])
    workspace = SimpleNamespace(jobs=_Jobs([_base_run(1), _base_run(2, tasks=[])]))

    primeira = backfill_timings(workspace, SETTINGS, SOURCE)
    segunda = backfill_timings(workspace, SETTINGS, SOURCE)

    assert [item.id for item in primeira] == [item.id for item in segunda]
    assert len(primeira) == 1
    assert workspace.jobs.chamadas[0]["start_time_from"] is None
    assert workspace.jobs.chamadas[0]["expand_tasks"] is True


def test_contagem_de_inseridos_vem_do_merge():
    from eict.adapters.store import inserted_count

    class _Resultado:
        def collect(self):
            return [{"num_inserted_rows": 0, "num_affected_rows": 0}]

    assert inserted_count(_Resultado(), 20) == 0


def test_sem_metrica_recua_para_o_enviado():
    from eict.adapters.store import inserted_count

    assert inserted_count(None, 20) == 20
