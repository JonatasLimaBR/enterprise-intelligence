"""Baseline de custo por run: a mesma estatística robusta do runtime, sobre dólares.

O incidente de custo só existe quando o custo sobe **sem** o tempo subir. Se a execução também
regrediu, o incidente de runtime já carrega o custo incremental — abrir outro duplicaria a fila.
Custo que sobe com o tempo parado aponta para outra coisa: classe de compute, ambiente,
`performance_target` — exatamente o que o runtime não enxerga.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from eict.domain.baseline import MIN_SAMPLES, WINDOW, threshold
from eict.domain.models import Run

FLOOR_USD = 0.05
POLICY_VERSION = "cost-robust-v1"


@dataclass(frozen=True)
class CostBaseline:
    median_usd: float
    mad_usd: float
    threshold_usd: float
    deciding_term: str
    n: int
    policy_version: str = POLICY_VERSION


@dataclass(frozen=True)
class CostVerdict:
    run_id: str
    cost_usd: float | None
    baseline: CostBaseline | None
    is_regression: bool
    reason: str = ""


def evaluate(
    run: Run,
    history: list[Run],
    costs: dict[str, float],
    excluded_run_ids: frozenset[str] = frozenset(),
    regime_start: datetime | None = None,
) -> CostVerdict:
    """Custo do run contra os `WINDOW` runs anteriores com custo, no regime vigente."""
    custo = costs.get(run.run_id)
    if custo is None:
        return CostVerdict(run.run_id, None, None, False, "custo ainda não disponível no billing")
    anteriores = sorted(
        (
            item
            for item in history
            if item.job_id == run.job_id
            and item.succeeded
            and item.run_id != run.run_id
            and item.end_time <= run.start_time
            and item.run_id not in excluded_run_ids
            and item.run_id in costs
            and (regime_start is None or item.start_time >= regime_start)
        ),
        key=lambda item: item.end_time,
    )[-WINDOW:]
    if len(anteriores) < MIN_SAMPLES:
        return CostVerdict(run.run_id, custo, None, False, f"baseline de custo com {len(anteriores)} runs")
    mediana, mad, limiar, termo = threshold([costs[item.run_id] for item in anteriores], floor=FLOOR_USD)
    baseline = CostBaseline(mediana, mad, limiar, termo, len(anteriores))
    return CostVerdict(run.run_id, custo, baseline, custo > limiar)


def summary(run: Run, verdict: CostVerdict, execution_ratio: float | None) -> str:
    base = verdict.baseline
    fator = verdict.cost_usd / base.median_usd if base and base.median_usd else 0.0
    tempo = (
        f"execução {execution_ratio:.1f}× a mediana — o tempo não explica"
        if execution_ratio is not None
        else "sem tempo de execução medido"
    )
    return (
        f"Run {run.run_id}: custo US$ {verdict.cost_usd:.4f} contra mediana US$ {base.median_usd:.4f} "
        f"({fator:.1f}×); limiar US$ {base.threshold_usd:.4f} pelo termo {base.deciding_term}, n={base.n}; {tempo}"
    )
