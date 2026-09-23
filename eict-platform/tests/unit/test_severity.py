"""A escada de severidade precisa ser total: um motor que eleva compara sempre."""

from __future__ import annotations

from eict.domain.contracts import SEVERITIES
from eict.domain.severity import (
    CEILING,
    LADDER,
    capped_at,
    highest,
    is_at_or_above,
    rank_of,
)


def test_at12_high_fica_acima_de_warning_e_abaixo_de_critical():
    """O bug original: `high` não estava na escada e caía abaixo de `warning`."""
    assert rank_of("warning") < rank_of("high") < rank_of("critical")


def test_a_escada_cobre_as_cinco_palavras_em_uso():
    assert LADDER == ("info", "warning", "high", "critical", "blocking")


def test_severidade_desconhecida_fica_no_piso():
    assert rank_of("inventada") == 0
    assert rank_of("inventada") <= rank_of("info")


def test_mais_alta_entre_varias():
    assert highest(["info", "high", "warning"]) == "high"
    assert highest(["blocking", "critical"]) == "blocking"


def test_mais_alta_de_lista_vazia_e_o_piso():
    assert highest([]) == "info"


def test_teto_corta_acima_de_critical():
    assert capped_at("blocking") == CEILING
    assert capped_at("warning") == "warning"
    assert capped_at("critical") == "critical"


def test_comparacao_de_ordem():
    assert is_at_or_above("critical", "high")
    assert is_at_or_above("high", "high")
    assert not is_at_or_above("warning", "high")


def test_contrato_declara_um_subconjunto_da_escada():
    """Contrato nunca declara `high`; `high` é emitido por incidente de runtime."""
    assert SEVERITIES < set(LADDER)
    assert "high" not in SEVERITIES
