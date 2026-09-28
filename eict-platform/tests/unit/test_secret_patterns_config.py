"""Carga do catálogo de padrões: válido, inválido, ausente e sem padrões → embutido."""

from __future__ import annotations

VALIDO = """
patterns:
  - name: meu_token
    regex: "MYT[0-9]{10}"
    severity: alta
entropy:
  min_len: 24
  min_bits: 4.5
mask_prefix: 6
"""


def test_catalogo_valido(tmp_path):
    from eict.adapters.secret_patterns import load_policy

    (tmp_path / "patterns.yaml").write_text(VALIDO, encoding="utf-8")
    policy = load_policy(tmp_path)

    assert [p.name for p in policy.patterns] == ["meu_token"]
    assert policy.entropy_min_len == 24
    assert policy.entropy_min_bits == 4.5
    assert policy.mask_prefix == 6


def test_ausente_usa_embutido(tmp_path):
    from eict.adapters.secret_patterns import DEFAULT_POLICY, load_policy

    assert load_policy(tmp_path) == DEFAULT_POLICY


def test_caminho_vazio_usa_embutido():
    from eict.adapters.secret_patterns import DEFAULT_POLICY, load_policy

    assert load_policy("") == DEFAULT_POLICY


def test_yaml_invalido_usa_embutido(tmp_path):
    from eict.adapters.secret_patterns import DEFAULT_POLICY, load_policy

    (tmp_path / "patterns.yaml").write_text("patterns: [1, 2\n", encoding="utf-8")
    assert load_policy(tmp_path) == DEFAULT_POLICY


def test_sem_padroes_validos_usa_embutido(tmp_path):
    from eict.adapters.secret_patterns import DEFAULT_POLICY, load_policy

    (tmp_path / "patterns.yaml").write_text("patterns: []\n", encoding="utf-8")
    assert load_policy(tmp_path) == DEFAULT_POLICY
