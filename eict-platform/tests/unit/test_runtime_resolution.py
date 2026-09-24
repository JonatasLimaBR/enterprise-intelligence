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


# --- baseline robusto: o roteiro da verificação real, em unidade ------------------------------

from dataclasses import replace  # noqa: E402

from eict.domain.regimes import parse_declaration  # noqa: E402

SHA_NOVO = "d" * 40


def _medido(index: int, execucao: float, setup: float = 130.0, sha: str | None = None, **extra):
    run = make_run(index, duration_s=execucao + setup, **({"git_sha": sha} if sha else {}), **extra)
    return replace(run, execution_s=execucao, setup_s=setup)


def _contaminada():
    """A história real do job pequeno: leves e `heavy` misturados, sem regime."""
    return [_medido(i, valor) for i, valor in enumerate([73, 113, 29, 95, 148, 27])]


def _declaracao():
    return parse_declaration(
        {
            "job_id": JOB_ID,
            "effective_from": {"git_sha": SHA_NOVO},
            "owner": "dados@exemplo.com",
            "reason": "baseline contaminado por runs heavy de teste",
        }
    )


def _leves(inicio: int, n: int = 5):
    return [_medido(inicio + i, 28.0 + (i % 3), sha=SHA_NOVO) for i in range(n)]


def _ciclo_regime(features, incidents=(), regimes=()):
    return correlate_job.correlate(
        None, Settings(), features, [], list(incidents), [], [], NOW, regimes=list(regimes)
    )


def test_mediana_resiste_a_contaminacao_minoritaria_mesmo_sem_regime(fake_store):
    """4 `heavy` entre 11 runs: mediana 29, limiar 59 — o p95 antigo ficava perto de 150."""
    historia = _contaminada() + _leves(6) + [_medido(11, 95.0, sha=SHA_NOVO)]

    touched = _ciclo_regime(_features(*historia))

    assert [item.first_run_id for item in touched] == ["run-11"]


def test_contaminacao_majoritaria_so_o_regime_resolve(fake_store):
    """Com os pesados em maioria, a mediana vira pesada; só o corte do regime devolve o sinal."""
    pesados = [_medido(i, valor) for i, valor in enumerate([113, 95, 148, 120, 101, 130, 99, 140])]
    historia = pesados + _leves(8) + [_medido(13, 95.0, sha=SHA_NOVO)]

    sem = _ciclo_regime(_features(*historia))
    com = _ciclo_regime(_features(*historia), regimes=[_declaracao()])

    assert sem == []
    assert [item.first_run_id for item in com] == ["run-13"]


def test_sc1_com_regime_declarado_o_pesado_abre_incidente(fake_store):
    historia = _contaminada() + _leves(6) + [_medido(11, 95.0, sha=SHA_NOVO)]

    touched = _ciclo_regime(_features(*historia), regimes=[_declaracao()])

    assert [item.first_run_id for item in touched] == ["run-11"]
    timeline = fake_store.rows[Settings().table("ops", "incident_timeline")]
    assert "execution 95s" in timeline[-1]["summary"]
    assert "duração total 225s" in timeline[-1]["summary"]


def test_sc2_um_leve_depois_fecha_o_incidente(fake_store):
    pesado = _medido(11, 95.0, sha=SHA_NOVO)
    historia = _contaminada() + _leves(6) + [pesado]
    abertos = _ciclo_regime(_features(*historia), regimes=[_declaracao()])

    touched = _ciclo_regime(
        _features(*historia, _medido(12, 29.0, sha=SHA_NOVO)), abertos, regimes=[_declaracao()]
    )

    assert touched[-1].state == "recovered"
    assert touched[-1].incident_id == abertos[0].incident_id


def test_sc4_regressao_central_segue_detectada_pela_execucao(fake_store):
    saudaveis = [_medido(i, valor) for i, valor in enumerate([25, 27, 26, 23, 26, 27, 42, 34, 31, 26, 28, 26])]
    lento = _medido(12, 1435.0, setup=134.0)

    touched = _ciclo_regime(_features(*saudaveis, lento))

    assert [item.first_run_id for item in touched] == ["run-12"]
    resumo = fake_store.rows[Settings().table("ops", "incident_timeline")][-1]["summary"]
    assert "(54.2×)" in resumo
    assert "duração total 1569s" in resumo


def test_sc6_setup_lento_nao_abre_incidente(fake_store):
    historia = [_medido(i, 28.0) for i in range(6)] + [_medido(6, 27.0, setup=285.0)]

    assert _ciclo_regime(_features(*historia)) == []
