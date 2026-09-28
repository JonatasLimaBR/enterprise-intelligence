"""Carga da config de pesos: válida, inválida, ausente e parcial → padrão."""

from __future__ import annotations

VALIDO = """
blast: 0.5
history: 0.2
size: 0.2
provenance: 0.1
band_high: 0.7
files_cap: 20
author_patterns:
  - "[bot]"
  - servico
"""


def test_config_valida(tmp_path):
    from eict.adapters.change_risk_config import load_weights

    (tmp_path / "weights.yaml").write_text(VALIDO, encoding="utf-8")
    w = load_weights(tmp_path)

    assert w.blast == 0.5
    assert w.band_high == 0.7
    assert w.files_cap == 20
    assert w.author_patterns == ("[bot]", "servico")


def test_ausente_usa_padrao(tmp_path):
    from eict.adapters.change_risk_config import load_weights
    from eict.domain.change_risk import ChangeRiskWeights

    assert load_weights(tmp_path) == ChangeRiskWeights()


def test_caminho_vazio_usa_padrao():
    from eict.adapters.change_risk_config import load_weights
    from eict.domain.change_risk import ChangeRiskWeights

    assert load_weights("") == ChangeRiskWeights()


def test_yaml_invalido_usa_padrao(tmp_path):
    from eict.adapters.change_risk_config import load_weights
    from eict.domain.change_risk import ChangeRiskWeights

    (tmp_path / "weights.yaml").write_text("blast: [1, 2\n", encoding="utf-8")
    assert load_weights(tmp_path) == ChangeRiskWeights()


def test_valor_invalido_mantem_o_resto(tmp_path):
    from eict.adapters.change_risk_config import load_weights

    (tmp_path / "weights.yaml").write_text("blast: nao_numero\nhistory: 0.9\n", encoding="utf-8")
    w = load_weights(tmp_path)

    assert w.history == 0.9
    assert w.blast == 0.40  # padrão mantido
