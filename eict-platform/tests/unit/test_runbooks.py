"""Runbooks versionados e a escolha por incidente (AT-01…05, AT-15, SC1, SC2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eict.adapters.runbook_loader import load_directory
from eict.domain.runbooks import APROVADO, RASCUNHO, RunbookError, applicable, parse

REPO = Path(__file__).resolve().parents[2] / "runbooks"


def _rb(runbook_id, tipos, hipoteses=(), dimensoes=(), status=APROVADO):
    return parse(
        {
            "runbook_id": runbook_id,
            "title": runbook_id,
            "status": status,
            "owner": "x@exemplo.com",
            "applies_to": {
                "incident_types": list(tipos),
                "hypothesis_codes": list(hipoteses),
                "dimensions": list(dimensoes),
            },
            "steps": ["passo"],
        }
    )


def test_at01_tipo_e_causa_vem_antes_de_so_tipo():
    especifico = _rb("RB-A", ["runtime_regression"], ["skew_join_change"])
    generico = _rb("RB-B", ["runtime_regression"])

    escolhidos = applicable([generico, especifico], "runtime_regression", "skew_join_change")

    assert [(item.runbook.runbook_id, item.reason) for item in escolhidos] == [
        ("RB-A", "tipo e causa"),
        ("RB-B", "tipo"),
    ]


def test_at02_so_tipo_quando_o_runbook_nao_restringe():
    [item] = applicable([_rb("RB-B", ["cost_regression"])], "cost_regression", "sem_hipotese")

    assert item.reason == "tipo"


def test_runbook_que_restringe_a_causa_e_nao_casa_fica_de_fora():
    rb = _rb("RB-A", ["runtime_regression"], ["skew_join_change"])

    assert applicable([rb], "runtime_regression", "volume_growth") == []


def test_at03_freshness_pela_dimensao():
    freshness = _rb("RB-002", ["contract_violation", "sla_risk"], dimensoes=["freshness"])

    [item] = applicable([freshness], "contract_violation", "pipeline_failure", frozenset({"freshness"}))

    assert item.reason == "tipo e dimensão"


def test_schema_nao_recebe_o_runbook_de_freshness():
    freshness = _rb("RB-002", ["contract_violation"], dimensoes=["freshness"])

    assert applicable([freshness], "contract_violation", "upstream_change", frozenset({"schema"})) == []


def test_sla_risk_sem_dimensao_casa_pelo_tipo():
    """A regra v1.1: restrição só vale para a informação que o incidente tem."""
    freshness = _rb("RB-002", ["contract_violation", "sla_risk"], dimensoes=["freshness"])

    [item] = applicable([freshness], "sla_risk", "sem_hipotese")

    assert item.reason == "tipo"


def test_at04_aprovado_antes_de_rascunho_no_mesmo_nivel():
    aprovado = _rb("RB-Z", ["contract_violation"], dimensoes=["schema"])
    rascunho = _rb("RB-A", ["contract_violation"], dimensoes=["schema"], status=RASCUNHO)

    escolhidos = applicable([rascunho, aprovado], "contract_violation", "x", frozenset({"schema"}))

    assert [item.runbook.status for item in escolhidos] == [APROVADO, RASCUNHO]


def test_at05_tipo_sem_runbook():
    assert applicable([_rb("RB-A", ["runtime_regression"])], "semantic_conflict", "sem_hipotese") == []


def test_at15_sem_passos_e_recusado_inteiro():
    payload = {
        "runbook_id": "RB-X", "title": "t", "status": APROVADO, "owner": "o",
        "applies_to": {"incident_types": []}, "steps": [],
    }
    with pytest.raises(RunbookError, match="ao menos um passo"):
        parse(payload, "RB-X.yaml")


def test_status_invalido_e_recusado():
    payload = {
        "runbook_id": "RB-X", "title": "t", "status": "publicado", "owner": "o",
        "applies_to": {"incident_types": []}, "steps": ["a"],
    }
    with pytest.raises(RunbookError, match="status"):
        parse(payload)


def test_sem_applies_to_e_recusado():
    with pytest.raises(RunbookError, match="applies_to"):
        parse({"runbook_id": "RB-X", "title": "t", "status": APROVADO, "owner": "o", "steps": ["a"]})


def test_id_repetido_recusa_os_dois(tmp_path):
    for nome in ("a.yaml", "b.yaml"):
        (tmp_path / nome).write_text(
            "runbook_id: RB-1\ntitle: t\nstatus: aprovado\nowner: o\n"
            "applies_to: {incident_types: []}\nsteps: [a]\n",
            encoding="utf-8",
        )

    resultado = load_directory(tmp_path)

    assert resultado.runbooks == ()
    assert "repetido" in resultado.errors[-1]


# --- os runbooks do repositório -----------------------------------------------------------------


def _repo():
    resultado = load_directory(REPO)
    assert resultado.errors == ()
    return list(resultado.runbooks)


def test_os_9_runbooks_do_repositorio_carregam():
    runbooks = _repo()

    assert len(runbooks) == 9
    assert sum(1 for item in runbooks if item.status == RASCUNHO) == 3


def test_sc1_incidente_central_da_demo_recebe_o_rb001():
    [primeiro, *_] = applicable(_repo(), "runtime_regression", "skew_join_change")

    assert primeiro.runbook.runbook_id == "RB-001"
    assert primeiro.reason == "tipo e causa"


def test_sc2_freshness_recebe_rb002_e_schema_o_rascunho():
    freshness = applicable(_repo(), "contract_violation", "pipeline_failure", frozenset({"freshness"}))
    schema = applicable(_repo(), "contract_violation", "upstream_change", frozenset({"schema"}))

    assert [item.runbook.runbook_id for item in freshness] == ["RB-002"]
    assert [(item.runbook.runbook_id, item.runbook.status) for item in schema] == [("RB-009", RASCUNHO)]


def test_toda_tipo_de_incidente_existente_tem_runbook():
    tipos = {
        "runtime_regression", "contract_violation", "quality_engine_failure",
        "semantic_conflict", "sla_risk", "cost_regression",
    }
    cobertos = {tipo for item in _repo() for tipo in item.incident_types}

    assert tipos <= cobertos


def test_runbooks_sem_disparo_ficam_no_catalogo():
    sem_disparo = {item.runbook_id for item in _repo() if not item.has_trigger}

    assert sem_disparo == {"RB-004", "RB-005"}
