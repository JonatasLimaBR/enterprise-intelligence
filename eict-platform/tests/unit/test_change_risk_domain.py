"""Domínio do change risk: sub-scores puros, banda e determinismo."""

from __future__ import annotations

from datetime import UTC, datetime

from eict.domain.change_risk import (
    BlastInput,
    ChangeRiskWeights,
    HistoryInput,
    band_of,
    provenance_subscore,
    score_change,
    size_subscore,
)
from eict.domain.models import Change

W = ChangeRiskWeights()
AGORA = datetime(2026, 9, 28, tzinfo=UTC)


def make_change(**over):
    base = dict(
        sha="abc123", repo="acme/eict", author="alice", committed_at=AGORA,
        message="fix bug", files=("a.py",), patch="+ linha\n- outra\n contexto\n",
    )
    base.update(over)
    return Change(**base)


def test_size_cresce_com_arquivos_e_linhas():
    pequeno = size_subscore(("a.py",), "+um\n", W)
    grande = size_subscore(tuple(f"f{i}.py" for i in range(10)), "\n".join("+x" for _ in range(400)), W)
    assert grande.value > pequeno.value
    assert grande.value == 1.0


def test_proveniencia_por_autor_bot():
    resultado = provenance_subscore("dependabot[bot]", "bump deps", W)
    assert resultado.value == 1.0
    assert "automação" in resultado.reason


def test_proveniencia_por_trailer():
    resultado = provenance_subscore("alice", "fix\n\nGenerated-by: agente", W)
    assert resultado.value == 1.0


def test_proveniencia_humano():
    assert provenance_subscore("alice", "fix bug", W).value == 0.0


def test_bandas():
    assert band_of(0.10, W) == "baixo"
    assert band_of(0.50, W) == "médio"
    assert band_of(0.80, W) == "alto"


def test_score_change_pondera_e_e_deterministico():
    blast = BlastInput(1.0, True, ("sales_daily",), "atinge consumo humano")
    history = HistoryInput(("inc-1", "inc-2", "inc-3"), "3 incidentes")
    a = score_change(make_change(), blast, history, W)
    b = score_change(make_change(), blast, history, W)
    assert a == b  # determinístico
    assert a.blast.value == 1.0
    assert a.history.value == 1.0
    assert a.band == "alto"


def test_history_satura_no_denom():
    from eict.domain.change_risk import history_subscore

    muitos = HistoryInput(tuple(f"inc-{i}" for i in range(10)), "muitos")
    assert history_subscore(muitos, W).value == 1.0
    assert history_subscore(HistoryInput((), "nenhum"), W).value == 0.0
