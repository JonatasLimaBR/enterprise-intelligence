"""Correlator de custo: custo que sobe sem o tempo subir."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from eict.domain.incidents import COST_REGRESSION
from eict.domain.models import RunFeatures
from eict.jobs.cost_regression import correlate_costs
from tests.conftest import BASE_TIME, JOB_ID, make_profile, make_run

NOW = BASE_TIME + timedelta(days=1)


def _run(index, execucao=30.0, env="env-v2-standard"):
    run = replace(make_run(index, 200, env_hash=env), execution_s=execucao, setup_s=150.0)
    return RunFeatures(run=run, profile=make_profile(run.run_id))


def _ciclo(features, custos, abertos=(), fechado_em=None):
    return correlate_costs(
        features,
        list(abertos),
        custos,
        [],
        {JOB_ID: fechado_em} if fechado_em else {},
        "demo",
        NOW,
    )


def _saudaveis(n=6):
    features = [_run(i) for i in range(n)]
    return features, {item.run_id: 0.48 + (i % 3) * 0.01 for i, item in enumerate(features)}


def test_custo_sobe_com_o_tempo_parado_abre_incidente():
    features, custos = _saudaveis()
    caro = _run(6, env="env-v3-performance")
    custos[caro.run_id] = 1.20

    touched, entries, evidences = _ciclo([*features, caro], custos)

    assert [(item.type, item.first_run_id, item.severity) for item in touched] == [
        (COST_REGRESSION, caro.run_id, "warning")
    ]
    assert "o tempo não explica" in entries[0].summary
    assert '"env_hash": "env-v3-performance"' in evidences[0][1].value


def test_custo_e_tempo_sobem_juntos_fica_com_o_runtime():
    """O incidente de runtime já carrega o custo incremental: não duplica a fila."""
    features, custos = _saudaveis()
    lento = _run(6, execucao=1400.0)
    custos[lento.run_id] = 5.0

    touched, _, _ = _ciclo([*features, lento], custos)

    assert touched == []


def test_custo_normal_nao_abre():
    features, custos = _saudaveis()
    normal = _run(6)
    custos[normal.run_id] = 0.50

    assert _ciclo([*features, normal], custos)[0] == []


def test_run_sem_billing_e_ignorado():
    features, custos = _saudaveis()

    assert _ciclo([*features, _run(6)], custos)[0] == []


def test_custo_volta_ao_normal_fecha():
    features, custos = _saudaveis()
    caro = _run(6)
    custos[caro.run_id] = 1.20
    abertos = _ciclo([*features, caro], custos)[0]
    normal = _run(7)
    custos[normal.run_id] = 0.49

    touched, entries, _ = _ciclo([*features, caro, normal], custos, abertos)

    assert touched[-1].state == "recovered"
    assert entries[-1].kind == "auto_resolved"


def test_fechado_nao_renasce_do_mesmo_run():
    features, custos = _saudaveis()
    caro = _run(6)
    custos[caro.run_id] = 1.20
    normal = _run(7)
    custos[normal.run_id] = 0.49

    touched, _, _ = _ciclo([*features, caro, normal], custos, fechado_em=normal.run.end_time)

    assert touched == []
