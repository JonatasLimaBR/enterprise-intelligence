"""Job change_risk: file→asset, blast, histórico e o commit real na banda alta."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eict.config import Settings
from eict.domain.change_risk import ChangeRiskWeights
from eict.domain.impact import Edge
from eict.domain.models import Change
from eict.jobs import change_risk

AGORA = datetime(2026, 9, 28, tzinfo=UTC)
W = ChangeRiskWeights()
SOURCES = (("sales_daily_small.py", "sales_daily"), ("customers.py", "customers"))


def make_change(**over):
    base = dict(
        sha="deadbeef", repo="acme/eict", author="alice", committed_at=AGORA - timedelta(days=2),
        message="fix", files=("path/to/sales_daily_small.py",), patch="+a\n-b\n",
    )
    base.update(over)
    return Change(**base)


def test_assets_for_casa_por_sufixo_e_basename():
    assert change_risk.assets_for(("x/sales_daily_small.py",), SOURCES) == ("sales_daily",)
    assert change_risk.assets_for(("nada.py",), SOURCES) == ()


def test_blast_sem_asset_e_zero():
    blast = change_risk.blast_for((), (), AGORA, W, Settings())
    assert blast.score == 0.0
    assert "sem asset" in blast.reason


def test_blast_alcanca_consumo_humano_crava_1():
    edges = (Edge("sales_daily", "", "DASHBOARD", "d1", AGORA),)
    blast = change_risk.blast_for(("sales_daily",), edges, AGORA, W, Settings())
    assert blast.reaches_human is True
    assert blast.score == 1.0


def test_blast_isolado_normaliza_abaixo_de_1():
    edges = (Edge("iso", "iso_gold", "TABLE", "t1", AGORA),)
    blast = change_risk.blast_for(("iso",), edges, AGORA, W, Settings())
    assert blast.reaches_human is False
    assert 0.0 < blast.score < 1.0


def test_history_conta_mesmo_asset_mas_nao_outro():
    incidents = [
        {"incident_id": "inc-mesmo", "affected_assets": ["sales_daily"], "detected_at": AGORA},
        {"incident_id": "inc-outro", "affected_assets": ["customers"], "detected_at": AGORA},
    ]
    changes_at = {"sales_daily": [AGORA - timedelta(days=1)]}
    history = change_risk.history_for(("sales_daily",), incidents, changes_at, W)
    assert history.incidents == ("inc-mesmo",)


def test_history_ignora_incidente_fora_da_janela():
    incidents = [{"incident_id": "inc-velho", "affected_assets": ["sales_daily"], "detected_at": AGORA}]
    changes_at = {"sales_daily": [AGORA - timedelta(days=40)]}
    assert change_risk.history_for(("sales_daily",), incidents, changes_at, W).incidents == ()


def test_9872c00_cai_na_banda_alta():
    """AT-10/SC6: o commit da regressão central toca sales_daily (→ dashboard) e o asset tem histórico."""
    commit = make_change(sha="9872c00", files=("jobs/sales_daily_small.py",), committed_at=AGORA - timedelta(days=5))
    edges = (Edge("sales_daily", "", "DASHBOARD", "d1", AGORA),)
    incidents = [
        {"incident_id": f"inc-{i}", "affected_assets": ["sales_daily"], "detected_at": AGORA - timedelta(days=d)}
        for i, d in enumerate((4, 3, 2))
    ]
    rows = change_risk.build_rows([commit], SOURCES, edges, incidents, W, AGORA, Settings())

    [linha] = rows
    assert linha["sha"] == "9872c00"
    assert linha["band"] == "alto"
    assert linha["blast_score"] == 1.0
    assert linha["history_score"] == 1.0
    assert "inc-0" in linha["history_reason"]


def test_build_rows_e_deterministico():
    edges = (Edge("sales_daily", "", "DASHBOARD", "d1", AGORA),)
    a = change_risk.build_rows([make_change()], SOURCES, edges, [], W, AGORA, Settings())
    b = change_risk.build_rows([make_change()], SOURCES, edges, [], W, AGORA, Settings())
    assert a[0]["total_score"] == b[0]["total_score"]
