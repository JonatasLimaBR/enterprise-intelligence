"""Read models de runbooks e conhecimento, com os runbooks reais do repositório."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from eict.adapters.runbook_loader import load_directory
from eict.jobs.knowledge import build_rows, violation_dimensions

AGORA = datetime(2026, 9, 25, 12, tzinfo=UTC)
RUNBOOKS = list(load_directory(Path(__file__).resolve().parents[2] / "runbooks").runbooks)
SALES = "workspace.eict_workload.sales_daily"


def _inc(i, tipo, state="detected", subject=SALES, dias=0, horas=2):
    detectado = AGORA - timedelta(days=dias)
    return {
        "incident_id": f"inc-{i}", "type": tipo, "state": state, "subject": subject,
        "detected_at": detectado, "updated_at": detectado + timedelta(hours=horas),
    }


def _build(incidentes, causas=None, dims=None, usos=(), candidatos=(), registros=None):
    return build_rows(
        RUNBOOKS, incidentes, causas or {}, dims or {}, list(usos), list(candidatos), registros or {}, AGORA
    )


def test_dimensao_lida_da_evidencia():
    evidencias = [
        {"incident_id": "a", "kind": "rule_violation", "value": json.dumps({"dimension": "freshness"})},
        {"incident_id": "a", "kind": "rule_violation", "value": json.dumps({"dimension": "volume"})},
        {"incident_id": "b", "kind": "rule_violation", "value": "não é json"},
    ]

    assert violation_dimensions(evidencias) == {"a": frozenset({"freshness", "volume"})}


def test_incidente_central_recebe_rb001():
    linhas = _build([_inc(1, "runtime_regression")], causas={"inc-1": "skew_join_change"})

    assert [(row["runbook_id"], row["reason"]) for row in linhas["incident_runbooks"]] == [("RB-001", "tipo e causa")]


def test_violacao_de_freshness_recebe_rb002_pela_evidencia():
    linhas = _build([_inc(1, "contract_violation")], dims={"inc-1": frozenset({"freshness"})})

    assert [row["runbook_id"] for row in linhas["incident_runbooks"]] == ["RB-002"]


def test_so_incidentes_ativos_recebem_runbook_e_semelhantes():
    linhas = _build([_inc(1, "cost_regression", state="recovered")])

    assert linhas["incident_runbooks"] == []
    assert linhas["similar_incidents"] == []


def test_semelhante_traz_o_que_o_problema_resolvido_ensinou():
    atual = _inc(1, "contract_violation")
    antigo = _inc(2, "contract_violation", state="recovered", dias=10)
    causas = {"inc-1": "pipeline_failure", "inc-2": "pipeline_failure"}
    assinatura = f"contract_violation|{SALES}|pipeline_failure"
    candidatos = [{"problem_id": "prb-1", "signature": assinatura, "status": "resolvido"}]
    registros = {"prb-1": {"fix_description": "agendar o produtor", "known_error": "manual", "workaround": "rodar"}}

    linhas = _build([atual, antigo], causas, candidatos=candidatos, registros=registros)

    [similar] = linhas["similar_incidents"]
    assert similar["fix_description"] == "agendar o produtor"
    [item] = linhas["knowledge_items"]
    assert item["runbook_id"] == "RB-002"
    assert "agendar o produtor" in item["suggestion"]


def test_eficacia_por_runbook():
    recuperado = _inc(1, "runtime_regression", state="recovered", dias=2, horas=10)
    usos = [{"runbook_id": "RB-001", "incident_id": "inc-1", "at": recuperado["detected_at"]}]

    [linha] = _build([recuperado], usos=usos)["runbook_efficacy"]

    assert (linha["successes"], linha["efficacy"], linha["small_sample"]) == (1, 1.0, True)


def test_catalogo_tem_os_9_runbooks():
    assert len(_build([])["runbooks"]) == 9
