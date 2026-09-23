"""A comparação entre o que se declara e o que o código calcula."""

from __future__ import annotations

from pathlib import Path

import pytest

from eict.domain.extraction import ObservedMetric, extract
from eict.domain.metrics import (
    COMPUTED_NOT_DECLARED,
    DECLARED_MISMATCH,
    DECLARED_NOT_COMPUTED,
    FORMULA_CONFLICT,
    GRAIN_CONFLICT,
    SYNONYM,
    MetricError,
    compare,
    parse_declaration,
)

WORKLOAD = Path(__file__).resolve().parents[3] / "eict-demo-workload" / "src"
SALES = "workspace.eict_workload.sales_daily"
LIQUIDO = "sum(amount * (1 - discount_pct / 100))"


def declarar(**kwargs):
    base = {
        "metric_id": "revenue",
        "asset": SALES,
        "formula": LIQUIDO,
        "grain": ["order_date", "region", "segment"],
        "owner": "comercial@exemplo.com",
        "status": "canonical",
        "version": "1.0.0",
    }
    return parse_declaration({**base, **kwargs})


def observar(metric_id="revenue", formula_hash="h1", grain=("d",), linha=10, **kwargs):
    base = {
        "metric_id": metric_id,
        "asset": SALES,
        "formula_raw": "F.sum('x')",
        "formula_hash": formula_hash,
        "grain": grain,
        "source_path": "a.py",
        "source_line": linha,
        "status": "extraida",
    }
    return ObservedMetric(**{**base, **kwargs})


def tipos(divergencias):
    return {item.kind for item in divergencias}


def test_a_declaracao_liquida_casa_com_o_codigo_real():
    """Se isto falhar, toda declaração correta viraria divergência."""
    codigo = (WORKLOAD / "sales_daily.py").read_text(encoding="utf-8")
    observadas = [
        item for item in extract(codigo, "sales_daily.py", SALES) if item.metric_id == "revenue"
    ]

    assert declarar().formula_hash == observadas[0].formula_hash


def test_at01_conflito_de_formula_no_codigo_real():
    codigo = (WORKLOAD / "sales_daily_small.py").read_text(encoding="utf-8")
    observadas = list(extract(codigo, "sales_daily_small.py", SALES))

    divergencias = compare([declarar()], observadas)
    conflito = next(item for item in divergencias if item.kind == FORMULA_CONFLICT)

    assert conflito.metric_id == "revenue"
    assert "sales_daily_small.py:33" in conflito.detail
    assert conflito.is_blocking


def test_at04_conflito_de_grao_no_codigo_real():
    codigo = (WORKLOAD / "sales_daily_small.py").read_text(encoding="utf-8")

    divergencias = compare([declarar()], list(extract(codigo, "s.py", SALES)))
    grao = next(item for item in divergencias if item.kind == GRAIN_CONFLICT)

    assert "order_date, region" in grao.detail


def test_at03_formulas_iguais_nao_geram_conflito():
    divergencias = compare([], [observar(linha=1), observar(linha=9)])

    assert FORMULA_CONFLICT not in tipos(divergencias)


def test_at05_nomes_diferentes_com_a_mesma_formula_sao_sinonimos():
    divergencias = compare([], [observar("receita"), observar("faturamento")])
    sinonimo = next(item for item in divergencias if item.kind == SYNONYM)

    assert "faturamento" in sinonimo.detail
    assert "receita" in sinonimo.detail


def test_at06_declarada_e_nao_calculada():
    divergencias = compare([declarar(metric_id="margem")], [observar("revenue")])
    ausente = next(item for item in divergencias if item.kind == DECLARED_NOT_COMPUTED)

    assert ausente.metric_id == "margem"
    assert "comercial@exemplo.com" in ausente.detail


def test_at07_calculada_e_nao_declarada():
    divergencias = compare([], [observar("ticket_medio")])
    orfa = next(item for item in divergencias if item.kind == COMPUTED_NOT_DECLARED)

    assert orfa.metric_id == "ticket_medio"


def test_calculada_sem_declaracao_aparece_uma_vez_so():
    divergencias = compare([], [observar("ticket_medio", linha=1), observar("ticket_medio", linha=2)])

    assert len([item for item in divergencias if item.kind == COMPUTED_NOT_DECLARED]) == 1


def test_declaracao_que_nao_corresponde_a_implementacao():
    divergencias = compare([declarar()], [observar(formula_hash="outra-coisa")])
    erro = next(item for item in divergencias if item.kind == DECLARED_MISMATCH)

    assert "declarado" in erro.detail
    assert erro.is_blocking


def test_uma_implementacao_correta_entre_varias_nao_gera_mismatch():
    correta = declarar().formula_hash

    divergencias = compare(
        [declarar()], [observar(formula_hash=correta), observar(formula_hash="outra")]
    )

    assert DECLARED_MISMATCH not in tipos(divergencias)


def test_at11_declaracao_proposta_nao_vale_como_verdade():
    proposta = declarar(metric_id="margem", status="proposed")

    divergencias = compare([proposta], [observar("revenue")])

    assert DECLARED_NOT_COMPUTED not in tipos(divergencias)


def test_metrica_ambigua_fica_fora_da_comparacao():
    divergencias = compare([], [observar(status="ambigua", formula_hash="x")])

    assert divergencias == ()


def test_metrica_sem_dono_e_recusada():
    with pytest.raises(MetricError):
        declarar(owner="")


def test_status_invalido_e_recusado():
    with pytest.raises(MetricError):
        declarar(status="rascunho")


def test_grao_vazio_e_recusado():
    with pytest.raises(MetricError):
        declarar(grain=[])
