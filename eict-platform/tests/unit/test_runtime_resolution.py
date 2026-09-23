"""AT-15 — regressão de runtime fecha quando o run mais recente volta ao baseline.

E só nesse caso: run que falhou pode ser curto por ter morrido cedo, e job sem baseline
suficiente não prova nada.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from eict.config import Settings
from eict.domain.incidents import RUNTIME_REGRESSION
from eict.domain.models import RunFeatures
from eict.jobs import correlate as correlate_job
from tests.conftest import BASE_TIME, JOB_ID, make_profile, make_run

NOW = BASE_TIME + timedelta(hours=12)


class _Store:
    """Captura as escritas; nenhuma consulta é necessária sem billing."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict]] = {}

    def merge_rows(self, spark, table, rows, keys) -> None:
        self.rows.setdefault(table, []).extend(rows)

    def insert_missing(self, spark, table, rows, key) -> None:
        self.rows.setdefault(table, []).extend(rows)

    def query(self, spark, sql):  # pragma: no cover - não deve ser chamado
        raise AssertionError(sql)


@pytest.fixture
def fake_store(monkeypatch) -> _Store:
    fake = _Store()
    for name in ("merge_rows", "insert_missing", "query"):
        monkeypatch.setattr(correlate_job.store, name, getattr(fake, name))
    return fake


def _features(*runs) -> list[RunFeatures]:
    return [RunFeatures(run=run, profile=make_profile(run.run_id)) for run in runs]


def _ciclo(features, incidents=(), closed_until=None):
    return correlate_job.correlate(
        None, Settings(), features, [], list(incidents), [], [], NOW, closed_until=closed_until
    )


BASELINE = [make_run(index, duration_s=1200 + index * 10) for index in range(6)]
LENTO = make_run(6, duration_s=3420)


def _aberto(fake_store):
    touched = _ciclo(_features(*BASELINE, LENTO))
    assert [item.type for item in touched] == [RUNTIME_REGRESSION]
    return touched


def test_at15_run_recente_no_baseline_resolve(fake_store):
    abertos = _aberto(fake_store)

    touched = _ciclo(_features(*BASELINE, LENTO, make_run(7, duration_s=1250)), abertos)

    assert touched[-1].state == "recovered"
    assert touched[-1].incident_id == abertos[0].incident_id
    timeline = fake_store.rows[Settings().table("ops", "incident_timeline")]
    assert timeline[-1]["kind"] == "auto_resolved"


def test_incidente_fechado_nao_renasce_do_mesmo_run_lento(fake_store):
    """O run lento continua no histórico depois do fechamento; ele não reabre nada."""
    abertos = _aberto(fake_store)
    recuperacao = make_run(7, duration_s=1250)
    fechado = _ciclo(_features(*BASELINE, LENTO, recuperacao), abertos)[-1]

    touched = _ciclo(
        _features(*BASELINE, LENTO, recuperacao),
        [],
        closed_until={JOB_ID: fechado.updated_at},
    )

    assert touched == []


def test_regressao_nova_depois_do_fechamento_abre_outro_incidente(fake_store):
    abertos = _aberto(fake_store)
    recuperacao = make_run(7, duration_s=1250)
    fechado = _ciclo(_features(*BASELINE, LENTO, recuperacao), abertos)[-1]
    fechamento = LENTO.end_time + timedelta(minutes=30)

    touched = _ciclo(
        _features(*BASELINE, LENTO, recuperacao, make_run(8, duration_s=3400)),
        [],
        closed_until={JOB_ID: fechamento},
    )

    assert [item.first_run_id for item in touched] == ["run-8"]
    assert touched[0].incident_id != fechado.incident_id


def test_regressao_ainda_presente_nao_resolve(fake_store):
    abertos = _aberto(fake_store)

    touched = _ciclo(_features(*BASELINE, LENTO), abertos)

    assert all(item.state != "recovered" for item in touched)


def test_run_que_falhou_curto_nao_prova_recuperacao(fake_store):
    abertos = _aberto(fake_store)

    touched = _ciclo(
        _features(*BASELINE, LENTO, make_run(7, duration_s=60, result_state="FAILED")), abertos
    )

    assert all(item.state != "recovered" for item in touched)


def test_job_sem_runs_no_ciclo_nao_resolve(fake_store):
    abertos = _aberto(fake_store)

    assert _ciclo([], abertos) == []


def test_runtime_state_usa_o_run_mais_recente_de_cada_job():
    saudavel = _features(make_run(7, duration_s=1250))[0]
    falho = _features(make_run(8, duration_s=60, result_state="FAILED"))[0]

    avaliados, violando = correlate_job.runtime_state(
        {JOB_ID: (saudavel, False), "outro": (falho, False)}
    )

    assert avaliados == {(JOB_ID, RUNTIME_REGRESSION)}
    assert violando == frozenset()
