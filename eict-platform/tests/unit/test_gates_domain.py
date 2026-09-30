"""Domínio do gate: precedência da policy (SPEC-009)."""

from __future__ import annotations

from eict.domain.gates import APROVACAO, BLOQUEADO, PERMITE, GatePolicy, evaluate

POLICY = GatePolicy()
ALTA = [{"severity": "alta"}]
MEDIA = [{"severity": "média"}]


def test_segredo_alta_bloqueia():
    d = evaluate({"sha": "c1", "band": "baixo"}, ALTA, [], POLICY)
    assert d.outcome == BLOQUEADO and d.rule == "segredo_alta"


def test_dependencia_alta_bloqueia():
    d = evaluate({"sha": "c1", "band": "baixo"}, [], ALTA, POLICY)
    assert d.outcome == BLOQUEADO and d.rule == "dependencia_alta"


def test_band_alto_requer_aprovacao():
    d = evaluate({"sha": "c1", "band": "alto"}, [], MEDIA, POLICY)
    assert d.outcome == APROVACAO and d.rule == "band_alto"


def test_band_medio_sem_finding_permite():
    d = evaluate({"sha": "c1", "band": "médio"}, [], [], POLICY)
    assert d.outcome == PERMITE and d.rule == "sem_gatilho"


def test_precedencia_segredo_vence_band_alto():
    d = evaluate({"sha": "c1", "band": "alto"}, ALTA, ALTA, POLICY)
    assert d.rule == "segredo_alta"  # segredo tem precedência


def test_regra_cita_spec009():
    d = evaluate({"sha": "c1", "band": "alto"}, [], [], POLICY)
    assert "SPEC-009" in d.reason


def test_deterministico():
    cr = {"sha": "c1", "band": "alto"}
    assert evaluate(cr, [], [], POLICY) == evaluate(cr, [], [], POLICY)
