"""Baseline de runtime: a quanto se compara um run para dizer que ele regrediu.

Três escolhas sustentam este módulo, todas medidas em runs reais:

- **A métrica é a execução, não a duração total.** Em serverless, a duração total inclui o
  setup do ambiente, que oscilou de 125s a 285s entre runs idênticos. Um run leve chegou a
  313s — 285 de setup e 27 de trabalho. O setup é ruído maior que o sinal.
- **Estatística robusta.** Mediana e MAD, não p95: um único run atípico (o 73s entre runs de
  ~28s) levava o p95 a esconder uma regressão de 95s.
- **Regime.** Só entram runs do regime vigente. Sem isso, um run lento antigo fica no
  baseline para sempre e eleva o limiar até nada mais disparar.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime

from eict.domain.models import Run

RATIO = 2.0
K_MAD = 5.0
FLOOR_S = 30.0
WINDOW = 20
MIN_SAMPLES = 5
POLICY_VERSION = "baseline-robust-v1"

EXECUTION = "execution"
TOTAL = "total"

RATIO_TERM = "ratio"
MAD_TERM = "mad"
FLOOR_TERM = "floor"

INSUFFICIENT_BASELINE = "insufficient_baseline"


@dataclass(frozen=True)
class Baseline:
    median_s: float
    mad_s: float
    threshold_s: float
    deciding_term: str
    n: int
    metric: str = EXECUTION
    band: int | None = None
    band_fallback: bool = False
    regime_start: datetime | None = None
    policy_version: str = POLICY_VERSION


@dataclass(frozen=True)
class RegressionVerdict:
    is_regression: bool
    baseline: Baseline | None
    reason: str | None = None
    value_s: float | None = None
    metric: str = EXECUTION


def metric_of(run: Run) -> tuple[float, str]:
    """Execução quando medida; senão a duração total — e o nome de qual foi usada."""
    if run.execution_s is not None:
        return float(run.execution_s), EXECUTION
    return float(run.duration_s), TOTAL


def volume_band(run: Run) -> int | None:
    """`floor(log2(linhas))`: 4,8M e 6,0M caem na mesma faixa; 60M, em outra."""
    if not run.input_rows or run.input_rows <= 0:
        return None
    return int(math.floor(math.log2(run.input_rows)))


def threshold(sample: list[float]) -> tuple[float, float, float, str]:
    """Mediana, MAD, limiar e o termo que decidiu o limiar.

    O limiar é o maior de três: a razão pega a regressão proporcional, o MAD tolera a
    dispersão natural sem ser arrastado por um atípico, e o piso impede alerta em job de
    30s por variação de 10s. `MAD = 0` é seguro: os outros dois termos continuam valendo.
    """
    median = statistics.median(sample)
    mad = statistics.median(abs(value - median) for value in sample)
    termos = {
        RATIO_TERM: RATIO * median,
        MAD_TERM: median + K_MAD * mad,
        FLOOR_TERM: median + FLOOR_S,
    }
    termo = max(termos, key=lambda nome: termos[nome])
    return median, mad, termos[termo], termo


def compute_baseline(
    history: list[Run],
    before: Run,
    excluded_run_ids: frozenset[str] = frozenset(),
    regime_start: datetime | None = None,
) -> Baseline | None:
    _, metric = metric_of(before)
    elegiveis = [
        run
        for run in history
        if run.succeeded
        and run.job_id == before.job_id
        and run.run_id != before.run_id
        and run.end_time <= before.start_time
        and run.run_id not in excluded_run_ids
        and (regime_start is None or run.start_time >= regime_start)
        and metric_of(run)[1] == metric
    ]
    elegiveis.sort(key=lambda run: run.end_time)

    band = volume_band(before)
    da_faixa = [run for run in elegiveis if band is not None and volume_band(run) == band]
    usar_faixa = len(da_faixa[-WINDOW:]) >= MIN_SAMPLES
    amostra = (da_faixa if usar_faixa else elegiveis)[-WINDOW:]
    if len(amostra) < MIN_SAMPLES:
        return None

    median, mad, limiar, termo = threshold([metric_of(run)[0] for run in amostra])
    return Baseline(
        median_s=median,
        mad_s=mad,
        threshold_s=limiar,
        deciding_term=termo,
        n=len(amostra),
        metric=metric,
        band=band if usar_faixa else None,
        band_fallback=band is not None and not usar_faixa,
        regime_start=regime_start,
    )


def is_regression(run: Run, baseline: Baseline | None) -> bool:
    if baseline is None:
        return False
    value, metric = metric_of(run)
    return metric == baseline.metric and value > baseline.threshold_s


def evaluate(
    run: Run,
    history: list[Run],
    excluded_run_ids: frozenset[str] = frozenset(),
    regime_start: datetime | None = None,
) -> RegressionVerdict:
    value, metric = metric_of(run)
    baseline = compute_baseline(history, run, excluded_run_ids, regime_start)
    if baseline is None:
        return RegressionVerdict(False, None, INSUFFICIENT_BASELINE, value, metric)
    return RegressionVerdict(is_regression(run, baseline), baseline, None, value, metric)


def last_healthy_run(
    history: list[Run],
    before: Run,
    excluded_run_ids: frozenset[str] = frozenset(),
) -> Run | None:
    candidates = [
        run
        for run in history
        if run.succeeded
        and run.run_id != before.run_id
        and run.end_time <= before.start_time
        and run.run_id not in excluded_run_ids
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda run: run.end_time)
