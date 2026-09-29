"""Domínio da supply chain: parse de manifestos, comparação de versão e matching."""

from __future__ import annotations

from datetime import UTC, datetime

from eict.domain.models import Change
from eict.domain.supply_chain import (
    Advisory,
    Dependency,
    match,
    parse_dependencies,
    scan_change,
    version_lt,
    version_tuple,
)

AGORA = datetime(2026, 9, 29, tzinfo=UTC)
ADVISORIES = {"pyyaml": (Advisory("pyyaml", "5.4", "alta", "CVE-2020-14343"),)}

PYPROJECT = """
[project]
name = "x"
dependencies = ["pyyaml>=5.3", "requests>=2.32", "databricks-sdk[openai]>=0.30"]
[project.optional-dependencies]
dev = ["pytest>=8.0"]
"""


def test_version_tuple_e_comparacao():
    assert version_tuple("2.6.1") == (2, 6, 1)
    assert version_lt("5.3", "5.4") is True
    assert version_lt("5.4", "5.4") is False
    assert version_lt("2.31.0", "2.31") is False


def test_parse_pyproject_inclui_principais_e_opcionais():
    deps = {d.package: d.lower_bound for d in parse_dependencies(PYPROJECT, "pyproject.toml")}
    assert deps["pyyaml"] == "5.3"
    assert deps["databricks-sdk"] == "0.30"
    assert deps["pytest"] == "8.0"  # optional-dependencies


def test_parse_requirements():
    texto = "requests==2.32.1\n# comentário\n"
    deps = {d.package: d.lower_bound for d in parse_dependencies(texto, "requirements.txt")}
    assert deps == {"requests": "2.32.1"}


def test_parse_toml_invalido_devolve_vazio():
    assert parse_dependencies("[project\n", "pyproject.toml") == []


def test_match_vulneravel_e_corrigido():
    assert match(Dependency("pyyaml", "5.3", "f"), ADVISORIES)  # 5.3 < 5.4
    assert match(Dependency("pyyaml", "5.4", "f"), ADVISORIES) == []  # já corrigido
    assert match(Dependency("outro", "1.0", "f"), ADVISORIES) == []  # sem advisory


def test_scan_change_so_linhas_adicionadas():
    change = Change(
        sha="c1", repo="a/b", author="x", committed_at=AGORA, message="bump",
        files=("pyproject.toml",), patch="+ pyyaml>=5.3\n  requests>=2.32\n- pyyaml>=5.5\n",
    )
    findings = scan_change(change, ADVISORIES)
    assert [f.package for f in findings] == ["pyyaml"]
    assert findings[0].cve == "CVE-2020-14343"
    assert findings[0].sha == "c1"
