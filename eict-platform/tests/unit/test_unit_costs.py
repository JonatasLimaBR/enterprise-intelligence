"""Custo por unidade: fórmula, dono e `n` (AT-11…14, SC6)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from eict.domain.unit_costs import (
    AMOSTRA_PEQUENA,
    MEDIDO,
    NAO_MEDIDO,
    OPERACAO,
    POR_CICLO,
    POR_INCIDENTE,
    POR_MILHAO_LINHAS,
    POR_RUN,
    SEM_BASE,
    SUCESSO_NAO_VERIFICADO,
    RunCost,
    per_incident,
    per_million_rows,
    per_run,
    units_for_jobs,
)

INICIO = datetime(2026, 9, 1, tzinfo=UTC)
FIM = datetime(2026, 10, 1, tzinfo=UTC)


def _runs(*custos, job="j1", nome="sales"):
    return [RunCost(job, nome, f"r{i}", Decimal(str(custo))) for i, custo in enumerate(custos)]


def test_at11_so_runs_bem_sucedidos_com_n():
    runs = _runs(1, 2, 3, 100)
    unidade = per_run(POR_RUN, "sales", "dono", runs, {"r0": True, "r1": True, "r2": True, "r3": False})
    assert (unidade.median, unidade.mean, unidade.n) == (Decimal("2"), Decimal("2"), 3)
    assert unidade.status == AMOSTRA_PEQUENA
    assert unidade.formula and unidade.owner == "dono"


def test_at11_cinco_runs_ou_mais_e_medido():
    runs = _runs(1, 1, 1, 1, 1)
    assert per_run(POR_RUN, "s", "d", runs, {run.run_id: True for run in runs}).status == MEDIDO


def test_sem_nenhum_sucesso_e_sem_base():
    runs = _runs(1, 2)
    unidade = per_run(POR_RUN, "s", "d", runs, {"r0": False, "r1": False})
    assert (unidade.n, unidade.median, unidade.status) == (0, None, SEM_BASE)


def test_sem_estado_conhecido_usa_todos_e_avisa():
    unidade = per_run(POR_RUN, "s", "d", _runs(1, 3), {})
    assert (unidade.n, unidade.status, unidade.mean) == (2, SUCESSO_NAO_VERIFICADO, Decimal("2"))


def test_at12_custo_por_milhao_de_linhas():
    runs = _runs(2, 4)
    unidade = per_million_rows("s", "d", runs, {"r0": True, "r1": True}, {"r0": 1_000_000, "r1": 2_000_000})
    assert unidade.mean == Decimal("2")
    assert unidade.median == Decimal("2")
    assert unidade.n == 2


def test_at12_sem_profile_e_nao_medido():
    unidade = per_million_rows("s", "d", _runs(2), {"r0": True}, {"r0": None})
    assert (unidade.status, unidade.n, unidade.median) == (NAO_MEDIDO, 0, None)


def test_at13_custo_por_incidente_soma_o_incremental_e_dono_e_operacao():
    incidentes = [
        {"incident_id": "a", "detected_at": datetime(2026, 9, 3, tzinfo=UTC)},
        {"incident_id": "b", "detected_at": datetime(2026, 9, 4, tzinfo=UTC)},
        {"incident_id": "velho", "detected_at": datetime(2026, 8, 30, tzinfo=UTC)},
    ]
    custos = [
        {"incident_id": "a", "status": "available", "incremental_cost_usd": 0.03},
        {"incident_id": "a", "status": "available", "incremental_cost_usd": 0.01},
        {"incident_id": "b", "status": "pending", "incremental_cost_usd": None},
        {"incident_id": "velho", "status": "available", "incremental_cost_usd": 9.0},
    ]
    unidade, por_incidente = per_incident(incidentes, custos, INICIO, FIM)
    assert por_incidente == {"a": Decimal("0.04")}
    assert (unidade.unit, unidade.owner, unidade.n, unidade.median) == (POR_INCIDENTE, OPERACAO, 1, Decimal("0.04"))


def test_at14_ciclo_eict_recebe_custo_por_ciclo_e_os_demais_nao():
    runs = _runs(1, 3, job="c", nome="[dev x] eict-cycle-dev") + _runs(5, job="s", nome="sales")
    unidades = units_for_jobs(runs, {"c": "plataforma@x"}, {}, {}, frozenset({"eict-cycle"}))
    ciclo = [item for item in unidades if item.unit == POR_CICLO]
    assert len(ciclo) == 1
    assert (ciclo[0].mean, ciclo[0].owner, ciclo[0].n) == (Decimal("2"), "plataforma@x", 2)
    assert {item.unit for item in unidades if item.subject == "sales"} == {POR_RUN, POR_MILHAO_LINHAS}


def test_sc6_toda_unidade_tem_formula_dono_e_n():
    unidades = units_for_jobs(_runs(1, 2), {"j1": "dono"}, {}, {}, frozenset())
    assert all(item.formula and item.owner and item.n is not None for item in unidades)
