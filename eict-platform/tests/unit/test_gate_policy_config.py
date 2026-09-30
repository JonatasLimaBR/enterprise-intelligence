"""Carga da policy de gate: válida, inválida, ausente e valor inválido → padrão conservador."""

from __future__ import annotations


def test_policy_valida(tmp_path):
    from eict.adapters.gate_policy import load_policy

    (tmp_path / "policy.yaml").write_text(
        "outcomes:\n  band_alto: bloqueado\n  default: requer_aprovacao\n", encoding="utf-8"
    )
    policy = load_policy(tmp_path)

    assert policy.band_alto == "bloqueado"
    assert policy.default == "requer_aprovacao"
    assert policy.secret_high == "bloqueado"  # não sobrescrito → padrão


def test_ausente_usa_padrao(tmp_path):
    from eict.adapters.gate_policy import DEFAULT_POLICY, load_policy

    assert load_policy(tmp_path) == DEFAULT_POLICY


def test_caminho_vazio_usa_padrao():
    from eict.adapters.gate_policy import DEFAULT_POLICY, load_policy

    assert load_policy("") == DEFAULT_POLICY


def test_yaml_invalido_usa_padrao(tmp_path):
    from eict.adapters.gate_policy import DEFAULT_POLICY, load_policy

    (tmp_path / "policy.yaml").write_text("outcomes: [1, 2\n", encoding="utf-8")
    assert load_policy(tmp_path) == DEFAULT_POLICY


def test_valor_invalido_ignorado(tmp_path):
    from eict.adapters.gate_policy import load_policy

    (tmp_path / "policy.yaml").write_text("outcomes:\n  band_alto: xpto\n", encoding="utf-8")
    policy = load_policy(tmp_path)

    assert policy.band_alto == "requer_aprovacao"  # 'xpto' inválido → mantém padrão
