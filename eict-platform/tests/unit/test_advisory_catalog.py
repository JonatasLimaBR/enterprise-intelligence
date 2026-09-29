"""Carga do catálogo de advisories: válido, inválido, ausente e sem entradas → embutido."""

from __future__ import annotations

VALIDO = """
advisories:
  - package: Django
    fixed_in: "4.2.1"
    severity: alta
    cve: CVE-EXEMPLO
"""


def test_catalogo_valido_agrupa_por_pacote(tmp_path):
    from eict.adapters.advisory_catalog import load_advisories

    (tmp_path / "advisories.yaml").write_text(VALIDO, encoding="utf-8")
    adv = load_advisories(tmp_path)

    assert "django" in adv  # normalizado para minúsculo
    assert adv["django"][0].fixed_in == "4.2.1"


def test_ausente_usa_embutido(tmp_path):
    from eict.adapters.advisory_catalog import load_advisories

    adv = load_advisories(tmp_path)
    assert "pyyaml" in adv and "requests" in adv


def test_caminho_vazio_usa_embutido():
    from eict.adapters.advisory_catalog import load_advisories

    assert "pyyaml" in load_advisories("")


def test_yaml_invalido_usa_embutido(tmp_path):
    from eict.adapters.advisory_catalog import load_advisories

    (tmp_path / "advisories.yaml").write_text("advisories: [1, 2\n", encoding="utf-8")
    assert "pyyaml" in load_advisories(tmp_path)


def test_sem_entradas_validas_usa_embutido(tmp_path):
    from eict.adapters.advisory_catalog import load_advisories

    (tmp_path / "advisories.yaml").write_text("advisories: []\n", encoding="utf-8")
    assert "pyyaml" in load_advisories(tmp_path)
