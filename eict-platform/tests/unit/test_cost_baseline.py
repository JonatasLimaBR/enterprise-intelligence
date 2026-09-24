"""Baseline de custo por run."""

from __future__ import annotations

from dataclasses import replace

from eict.domain.baseline import FLOOR_TERM, RATIO_TERM
from eict.domain.cost_baseline import FLOOR_USD, evaluate, summary
from tests.conftest import make_run

CUSTOS_SAUDAVEIS = [0.48, 0.50, 0.47, 0.49, 0.51, 0.48]


def _historia(custos):
    runs = [replace(make_run(i, 200), execution_s=30.0) for i in range(len(custos))]
    return runs, {run.run_id: custo for run, custo in zip(runs, custos, strict=True)}


def _avaliar(custo_atual, custos=CUSTOS_SAUDAVEIS, **kwargs):
    runs, custos_por_run = _historia(custos)
    atual = replace(make_run(len(runs), 200), execution_s=30.0)
    custos_por_run[atual.run_id] = custo_atual
    return evaluate(atual, runs, custos_por_run, **kwargs), atual


def test_custo_dobrado_e_regressao():
    verdict, _ = _avaliar(1.10)

    assert verdict.is_regression
    assert verdict.baseline.median_usd == 0.485
    assert verdict.baseline.deciding_term == RATIO_TERM


def test_variacao_normal_nao_dispara():
    assert not _avaliar(0.53)[0].is_regression


def test_piso_protege_job_barato():
    """Job de um centavo que passa a três centavos: +200%, mas abaixo do piso."""
    verdict, _ = _avaliar(0.03, custos=[0.01] * 6)

    assert not verdict.is_regression
    assert verdict.baseline.threshold_usd == 0.01 + FLOOR_USD
    assert verdict.baseline.deciding_term == FLOOR_TERM


def test_sem_custo_no_billing_fica_pendente():
    runs, custos = _historia(CUSTOS_SAUDAVEIS)
    atual = make_run(len(runs), 200)

    verdict = evaluate(atual, runs, custos)

    assert verdict.cost_usd is None
    assert not verdict.is_regression
    assert "não disponível" in verdict.reason


def test_amostra_insuficiente():
    verdict, _ = _avaliar(5.0, custos=[0.5] * 4)

    assert verdict.baseline is None
    assert not verdict.is_regression


def test_regime_corta_o_custo_antigo():
    """Custos antigos altos saem da amostra quando o regime recomeça."""
    runs, custos = _historia([2.0] * 6 + [0.5] * 5)
    atual = make_run(11, 200)
    custos[atual.run_id] = 1.2

    sem_regime = evaluate(atual, runs, custos)
    com_regime = evaluate(atual, runs, custos, regime_start=runs[6].start_time)

    assert not sem_regime.is_regression
    assert com_regime.is_regression


def test_runs_excluidos_ficam_fora():
    runs, custos = _historia(CUSTOS_SAUDAVEIS + [3.0])
    atual = make_run(7, 200)
    custos[atual.run_id] = 1.1

    verdict = evaluate(atual, runs, custos, excluded_run_ids=frozenset({runs[-1].run_id}))

    assert verdict.baseline.n == 6
    assert verdict.is_regression


def test_resumo_diz_que_o_tempo_nao_explica():
    verdict, atual = _avaliar(1.10)

    texto = summary(atual, verdict, 1.0)

    assert "US$ 1.1000" in texto
    assert "(2.3×)" in texto
    assert "o tempo não explica" in texto
