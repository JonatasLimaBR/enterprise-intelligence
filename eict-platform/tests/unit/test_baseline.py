from __future__ import annotations

from eict.domain.baseline import (
    INSUFFICIENT_BASELINE,
    compute_baseline,
    evaluate,
    is_regression,
    last_healthy_run,
)
from tests.conftest import make_run


def test_at001_regression_detected_above_p95_factor(healthy_history):
    regressed = make_run(8, duration_s=3420)

    verdict = evaluate(regressed, healthy_history)

    assert verdict.is_regression is True
    assert verdict.baseline is not None
    assert verdict.baseline.n == 7


def test_at002_insufficient_baseline_yields_no_incident():
    history = [make_run(index, duration_s=1200) for index in range(3)]
    regressed = make_run(4, duration_s=3420)

    verdict = evaluate(regressed, history)

    assert verdict.is_regression is False
    assert verdict.reason == INSUFFICIENT_BASELINE


def test_at003_failed_runs_excluded_from_baseline(healthy_history):
    polluted = [*healthy_history, make_run(7, duration_s=9000, result_state="FAILED")]
    current = make_run(8, duration_s=1800)

    baseline = compute_baseline(polluted, current)

    assert baseline is not None
    assert baseline.n == 7
    assert baseline.median_s < 1400


def test_baseline_ignores_runs_after_the_evaluated_run(healthy_history):
    current = make_run(3, duration_s=3000)

    baseline = compute_baseline(healthy_history, current)

    assert baseline is None


def test_excluded_run_ids_are_dropped(healthy_history):
    current = make_run(8, duration_s=1800)

    kept = compute_baseline(healthy_history, current, frozenset({"run-0", "run-1"}))
    dropped_below_minimum = compute_baseline(
        healthy_history, current, frozenset({"run-0", "run-1", "run-2"})
    )

    assert kept is not None
    assert kept.n == 5
    assert dropped_below_minimum is None


def test_is_regression_without_baseline_is_false():
    assert is_regression(make_run(1, duration_s=9999), None) is False


def test_last_healthy_run_returns_latest_successful(healthy_history):
    current = make_run(8, duration_s=3420)

    healthy = last_healthy_run(healthy_history, current)

    assert healthy is not None
    assert healthy.run_id == "run-6"


def test_last_healthy_run_skips_runs_attributed_to_an_incident(healthy_history):
    regressed_first = make_run(7, duration_s=3420)
    history = [*healthy_history, regressed_first]
    current = make_run(8, duration_s=3500)

    naive = last_healthy_run(history, current)
    aware = last_healthy_run(history, current, frozenset({regressed_first.run_id}))

    assert naive is not None and naive.run_id == regressed_first.run_id
    assert aware is not None and aware.run_id == "run-6"


# --- baseline robusto (EICT_ROBUST_BASELINE) -------------------------------------------------
# Os números vêm dos runs medidos em 2026-09-23: execução separada do setup.

from dataclasses import replace  # noqa: E402
from datetime import timedelta  # noqa: E402

from eict.domain.baseline import (  # noqa: E402
    EXECUTION,
    FLOOR_TERM,
    RATIO_TERM,
    TOTAL,
    WINDOW,
    threshold,
    volume_band,
)
from tests.conftest import BASE_TIME  # noqa: E402

GRANDE_SAUDAVEL = [25, 27, 26, 23, 26, 27, 42, 34, 31, 26, 28, 26]


def _run(index: int, execucao: float | None, setup: float = 130.0, linhas: int | None = None):
    run = make_run(index, duration_s=(execucao or 0) + setup, input_rows=linhas)
    return replace(run, execution_s=execucao, setup_s=setup if execucao is not None else None)


def _historia(execucoes, linhas=None):
    return [_run(index, valor, linhas=linhas) for index, valor in enumerate(execucoes)]


def test_at02_regressao_central_pela_execucao():
    historia = _historia(GRANDE_SAUDAVEL)
    lento = _run(len(historia), 1435.0)

    verdict = evaluate(lento, historia)

    assert verdict.is_regression
    assert verdict.baseline.median_s == 26.5
    assert verdict.baseline.mad_s == 1.0
    assert verdict.baseline.threshold_s == 56.5
    assert verdict.baseline.deciding_term == FLOOR_TERM
    assert verdict.metric == EXECUTION


def test_saudavel_de_42s_nao_dispara():
    historia = _historia(GRANDE_SAUDAVEL)

    assert not evaluate(_run(len(historia), 42.0), historia).is_regression


def test_at01_setup_lento_nao_e_regressao():
    """O run de 313s: 285 de setup, 27 de trabalho."""
    historia = _historia([29, 27, 28, 30, 27])
    run = _run(5, 27.0, setup=285.0)

    assert run.duration_s == 312.0
    assert not evaluate(run, historia).is_regression


def test_at03_outlier_nao_arrasta_o_limiar():
    historia = _historia([73, 29, 27, 28, 30])

    verdict = evaluate(_run(5, 95.0), historia)

    assert verdict.is_regression
    assert verdict.baseline.median_s == 29
    assert verdict.baseline.threshold_s == 59


def test_o_outlier_dentro_da_amostra_nao_move_o_limiar():
    """Com ou sem o 73s na amostra, o limiar fica em 58–59. Com p95, subiria a ~105."""
    _, _, com_outlier, _ = threshold([73, 29, 27, 28, 30])
    _, _, sem_outlier, _ = threshold([29, 29, 27, 28, 30])

    assert com_outlier == 59
    assert sem_outlier == 59


def test_run_de_73s_contra_baseline_de_28s_e_regressao():
    """O 73s real foi o primeiro run do job: nunca teve baseline. Julgado hoje, seria 2,5×."""
    historia = _historia([29, 27, 28, 30, 27])

    assert evaluate(_run(5, 73.0), historia).is_regression


def test_at04_piso_absoluto_protege_job_curto():
    median, mad, limiar, termo = threshold([10, 10.5, 9.5, 10, 10.5, 9.5, 10])

    assert median == 10 and limiar == 40 and termo == FLOOR_TERM


def test_job_longo_decide_pela_razao():
    """O caso desfavorável documentado em D3: +83% num job de 600s não dispara."""
    amostra = [580, 600, 620, 590, 610, 600, 640, 560]
    _, _, limiar, termo = threshold(amostra)

    assert termo == RATIO_TERM
    assert limiar == 1200


def test_mad_zero_nao_quebra():
    _, mad, limiar, termo = threshold([30, 30, 30, 30, 30])

    assert mad == 0 and limiar == 60 and termo in {RATIO_TERM, FLOOR_TERM}


def test_at05_amostra_insuficiente():
    historia = _historia([29, 27, 28, 30])

    verdict = evaluate(_run(4, 500.0), historia)

    assert not verdict.is_regression
    assert verdict.reason == INSUFFICIENT_BASELINE


def test_at06_janela_usa_so_os_20_mais_recentes():
    antigos = [500.0] * 10
    recentes = [30.0] * WINDOW
    historia = _historia(antigos + recentes)

    baseline = compute_baseline(historia, _run(len(historia), 30.0))

    assert baseline.n == WINDOW
    assert baseline.median_s == 30


def test_regime_corta_a_historia_anterior():
    """Os três `heavy` antigos do job pequeno não contaminam o regime seguinte."""
    contaminada = _historia([73, 113, 29, 95, 148, 27, 28, 30, 29, 27])
    inicio = contaminada[5].start_time

    sem_regime = evaluate(_run(10, 95.0), contaminada)
    com_regime = evaluate(_run(10, 95.0), contaminada, regime_start=inicio)

    assert com_regime.is_regression
    assert com_regime.baseline.n == 5
    assert com_regime.baseline.regime_start == inicio
    assert sem_regime.baseline.median_s > com_regime.baseline.median_s


def test_at13_faixa_de_volume_com_amostra():
    pequenos = [_run(i, 28.0, linhas=5_000_000) for i in range(5)]
    grandes = [_run(i + 5, 300.0, linhas=60_000_000) for i in range(5)]

    verdict = evaluate(_run(10, 95.0, linhas=4_800_000), pequenos + grandes)

    assert verdict.is_regression
    assert verdict.baseline.band == 22
    assert not verdict.baseline.band_fallback


def test_at14_faixa_sem_amostra_recua_sinalizada():
    historia = [_run(i, 28.0, linhas=5_000_000) for i in range(3)] + [
        _run(i + 3, 28.0, linhas=60_000_000) for i in range(3)
    ]

    baseline = compute_baseline(historia, _run(6, 28.0, linhas=5_000_000))

    assert baseline.band is None
    assert baseline.band_fallback
    assert baseline.n == 6


def test_at15_sem_execucao_compara_pela_total_sem_misturar():
    com_execucao = _historia([28, 29, 27, 30, 28])
    sem_execucao = [_run(i + 5, None, setup=0.0) for i in range(5)]
    for index, run in enumerate(sem_execucao):
        sem_execucao[index] = replace(run, duration_s=160.0)
    atual = replace(_run(10, None), duration_s=400.0)

    verdict = evaluate(atual, com_execucao + sem_execucao)

    assert verdict.metric == TOTAL
    assert verdict.baseline.metric == TOTAL
    assert verdict.baseline.n == 5
    assert verdict.is_regression


def test_faixa_por_log2():
    assert volume_band(make_run(0, 1, input_rows=4_799_931)) == 22
    assert volume_band(make_run(0, 1, input_rows=5_999_171)) == 22
    assert volume_band(make_run(0, 1, input_rows=60_000_000)) == 25
    assert volume_band(make_run(0, 1, input_rows=None)) is None


def test_runs_de_outro_job_nao_entram():
    historia = _historia([28, 29, 27, 30, 28])
    alheio = [replace(run, job_id="outro", run_id=f"x{i}") for i, run in enumerate(_historia([500] * 5))]

    baseline = compute_baseline(historia + alheio, _run(5, 30.0))

    assert baseline.median_s == 28


def test_regime_no_futuro_do_run_deixa_sem_baseline():
    historia = _historia([28, 29, 27, 30, 28])

    verdict = evaluate(_run(5, 95.0), historia, regime_start=BASE_TIME + timedelta(days=1))

    assert verdict.reason == INSUFFICIENT_BASELINE
