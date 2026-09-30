"""Job jev_advisor: egress off por padrão e coleta de calls nas zonas cinzentas."""

from __future__ import annotations

from datetime import UTC, datetime

from eict.config import Settings
from eict.jobs import jev_advisor

AGORA = datetime(2026, 9, 30, tzinfo=UTC)


def test_main_desligado_por_padrao_nao_faz_nada():
    # jev_dir vazio → nenhum advisor habilitado → retorna sem tocar spark/rede
    assert jev_advisor.main(["--jev-dir="]) is None


def test_collect_calls_cobre_as_tres_zonas(monkeypatch):
    def fake_query(spark, sql):
        if "connector_health" in sql:
            return [{"connector": "github", "status": "degradado", "detail": "422"}]
        if "incident_runbooks" in sql:
            return [{"incident_id": "i1", "incident_type": "t", "candidate_ids": ["RB-1", "RB-2"]}]
        if "incidents" in sql:
            return [{"incident_id": "i2", "type": "runtime_regression", "severity": "high",
                     "impact_score": 1.0, "affected_assets": ["a"], "escalated_from": ""}]
        return []

    monkeypatch.setattr(jev_advisor.store, "query", fake_query)
    calls = jev_advisor.collect_calls(None, Settings(), frozenset({"triage", "connector", "runbook"}), AGORA)
    advisors = {c.advisor for c in calls}

    assert advisors == {"triage", "connector", "runbook"}


def test_collect_calls_so_habilitados(monkeypatch):
    monkeypatch.setattr(jev_advisor.store, "query", lambda spark, sql: [])
    assert jev_advisor.collect_calls(None, Settings(), frozenset(), AGORA) == []


def test_loaders_toleram_tabela_ausente(monkeypatch):
    def boom(spark, sql):
        raise RuntimeError("tabela não existe")

    monkeypatch.setattr(jev_advisor.store, "query", boom)
    assert jev_advisor.load_degraded_connectors(None, Settings()) == []
    assert jev_advisor.load_tied_runbooks(None, Settings()) == []
