"""Custo por unidade de trabalho: cada unidade com fórmula, dono e `n`.

Run sem estado conhecido não entra calado na média de sucessos: se nenhum run do job tem estado,
a unidade usa todos e se declara `sucesso_nao_verificado`.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from eict.domain.allocation import normalize

MEDIDO = "medido"
AMOSTRA_PEQUENA = "amostra_pequena"
SEM_BASE = "sem_base"
NAO_MEDIDO = "nao_medido"
SUCESSO_NAO_VERIFICADO = "sucesso_nao_verificado"

SMALL_SAMPLE = 5
MILLION = Decimal("1000000")
OPERACAO = "operação"
CYCLE_JOB = "eict-cycle"

POR_RUN = "custo_por_run"
POR_MILHAO_LINHAS = "custo_por_milhao_linhas"
POR_INCIDENTE = "custo_por_incidente"
POR_CICLO = "custo_por_ciclo_eict"

FORMULAS = {
    POR_RUN: "mediana e média de Σ custo por job_run_id, runs bem-sucedidos do período",
    POR_MILHAO_LINHAS: "Σ custo dos runs ÷ Σ input_rows × 10⁶, runs bem-sucedidos com input_rows > 0",
    POR_INCIDENTE: "Σ incremental_cost_usd dos runs do incidente; mediana e média entre incidentes do período",
    POR_CICLO: "custo por run do job eict-cycle, runs bem-sucedidos do período",
}


@dataclass(frozen=True)
class RunCost:
    job_id: str
    job_name: str
    run_id: str
    cost: Decimal


@dataclass(frozen=True)
class UnitCost:
    unit: str
    subject: str
    owner: str
    formula: str
    median: Decimal | None
    mean: Decimal | None
    n: int
    status: str


def _status(n: int) -> str:
    if n == 0:
        return SEM_BASE
    return AMOSTRA_PEQUENA if n < SMALL_SAMPLE else MEDIDO


def _chosen(runs: list[RunCost], succeeded: dict[str, bool | None]) -> tuple[list[RunCost], bool]:
    """Runs bem-sucedidos; sem nenhum estado conhecido, todos — e o aviso."""
    conhecidos = [run for run in runs if succeeded.get(run.run_id) is not None]
    if not conhecidos:
        return list(runs), False
    return [run for run in conhecidos if succeeded[run.run_id]], True


def per_run(
    unit: str, subject: str, owner: str, runs: list[RunCost], succeeded: dict[str, bool | None]
) -> UnitCost:
    escolhidos, verificado = _chosen(runs, succeeded)
    valores = [run.cost for run in escolhidos]
    status = _status(len(valores))
    if valores and not verificado:
        status = SUCESSO_NAO_VERIFICADO
    return UnitCost(
        unit, subject, owner, FORMULAS[unit],
        statistics.median(valores) if valores else None,
        statistics.mean(valores) if valores else None,
        len(valores), status,
    )


def per_million_rows(
    subject: str, owner: str, runs: list[RunCost], succeeded: dict[str, bool | None], input_rows: dict[str, int | None]
) -> UnitCost:
    escolhidos, verificado = _chosen(runs, succeeded)
    medidos = [run for run in escolhidos if (input_rows.get(run.run_id) or 0) > 0]
    if not medidos:
        return UnitCost(POR_MILHAO_LINHAS, subject, owner, FORMULAS[POR_MILHAO_LINHAS], None, None, 0, NAO_MEDIDO)
    razoes = [run.cost / Decimal(input_rows[run.run_id]) * MILLION for run in medidos]
    agregado = sum((run.cost for run in medidos), Decimal("0")) / Decimal(
        sum(input_rows[run.run_id] for run in medidos)
    ) * MILLION
    status = _status(len(medidos)) if verificado else SUCESSO_NAO_VERIFICADO
    return UnitCost(
        POR_MILHAO_LINHAS, subject, owner, FORMULAS[POR_MILHAO_LINHAS],
        statistics.median(razoes), agregado, len(medidos), status,
    )


def per_incident(
    incidents: list[dict], run_costs: list[dict], start: datetime, end: datetime
) -> tuple[UnitCost, dict[str, Decimal]]:
    """Custo incremental somado por incidente detectado no período; só custo `available`."""
    no_periodo = {
        item["incident_id"]
        for item in incidents
        if item.get("detected_at") is not None and start <= item["detected_at"] < end
    }
    por_incidente: dict[str, Decimal] = {}
    for linha in run_costs:
        incidente = linha.get("incident_id")
        valor = linha.get("incremental_cost_usd")
        if incidente not in no_periodo or linha.get("status") != "available" or valor is None:
            continue
        por_incidente[incidente] = por_incidente.get(incidente, Decimal("0")) + Decimal(str(valor))
    valores = list(por_incidente.values())
    unidade = UnitCost(
        POR_INCIDENTE, "todos os incidentes", OPERACAO, FORMULAS[POR_INCIDENTE],
        statistics.median(valores) if valores else None,
        statistics.mean(valores) if valores else None,
        len(valores), _status(len(valores)),
    )
    return unidade, por_incidente


def units_for_jobs(
    runs: list[RunCost],
    owners: dict[str, str],
    succeeded: dict[str, bool | None],
    input_rows: dict[str, int | None],
    cycle_job_names: frozenset[str],
) -> list[UnitCost]:
    """Por run e por milhão de linhas de cada job; por ciclo para o job do ciclo EICT."""
    por_job: dict[str, list[RunCost]] = {}
    for run in runs:
        por_job.setdefault(run.job_id, []).append(run)
    unidades: list[UnitCost] = []
    for job_id in sorted(por_job, key=lambda item: (por_job[item][0].job_name, item)):
        lista = por_job[job_id]
        nome = lista[0].job_name or job_id
        dono = owners.get(job_id, "")
        unidades.append(per_run(POR_RUN, nome, dono, lista, succeeded))
        unidades.append(per_million_rows(nome, dono, lista, succeeded, input_rows))
        if normalize(nome) in cycle_job_names:
            unidades.append(per_run(POR_CICLO, nome, dono, lista, succeeded))
    return unidades
