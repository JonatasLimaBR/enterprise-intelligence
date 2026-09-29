"""Job supply_chain + integração no change_risk (piso 'alto' e contribuidores)."""

from __future__ import annotations

from datetime import UTC, datetime

from eict.adapters.advisory_catalog import load_advisories
from eict.adapters.github import GitHubError
from eict.domain.change_risk import ChangeRisk, SubScore
from eict.domain.models import Change
from eict.jobs import change_risk, supply_chain

AGORA = datetime(2026, 9, 29, tzinfo=UTC)
ADV = load_advisories("")  # embutido: pyyaml fixed_in 5.4 (alta), requests 2.31.0 (média)

PYPROJECT = '[project]\nname="x"\ndependencies = ["pyyaml>=5.3"]\n'


class _ClientOk:
    def fetch_file(self, path, ref=""):
        return PYPROJECT if path == "pyproject.toml" else ""


class _ClientErro:
    def fetch_file(self, path, ref=""):
        raise GitHubError("boom", 500)


def _risk(band="baixo"):
    zero = SubScore(0.0, "-")
    return ChangeRisk("c1", 0.1, band, zero, zero, zero, zero, ())


def test_build_sbom_parseia_manifesto():
    inv = supply_chain.build_sbom(_ClientOk())
    assert ("pyyaml", "5.3", "pyproject.toml") in inv


def test_build_sbom_sem_cliente_e_vazio():
    assert supply_chain.build_sbom(None) == []


def test_build_sbom_fetch_falho_e_vazio():
    assert supply_chain.build_sbom(_ClientErro()) == []


def test_inventory_findings_casa_vulneravel():
    inv = [("pyyaml", "5.3", "pyproject.toml")]
    findings = supply_chain.inventory_findings(inv, ADV)
    assert findings and findings[0].package == "pyyaml" and findings[0].sha == ""


def test_build_finding_rows_inclui_inventario_e_commit():
    inv = [("pyyaml", "5.3", "pyproject.toml")]
    change = Change(
        sha="c9", repo="a/b", author="x", committed_at=AGORA, message="bump",
        files=("pyproject.toml",), patch="+ requests>=2.20\n",
    )
    rows = supply_chain.build_finding_rows(inv, [change], ADV, AGORA)
    pacotes = {(r["package"], r["sha"]) for r in rows}
    assert ("pyyaml", "") in pacotes       # inventário
    assert ("requests", "c9") in pacotes    # do commit


def test_apply_dependencies_alta_impoe_piso():
    findings = [{"package": "pyyaml", "cve": "CVE-x", "severity": "alta"}]
    resultado = change_risk.apply_dependencies(_risk("baixo"), findings)
    assert resultado.band == "alto"
    assert any("pyyaml" in c for c in resultado.contributors)


def test_apply_dependencies_media_nao_impoe_piso():
    findings = [{"package": "requests", "cve": "CVE-y", "severity": "média"}]
    assert change_risk.apply_dependencies(_risk("baixo"), findings).band == "baixo"


def test_change_risk_build_rows_usa_dep_findings():
    from eict.config import Settings

    change = Change(
        sha="c9", repo="a/b", author="x", committed_at=AGORA, message="bump",
        files=("pyproject.toml",), patch="+ pyyaml>=5.3\n",
    )
    dep_findings = {"c9": [{"package": "pyyaml", "cve": "CVE-x", "severity": "alta"}]}
    rows = change_risk.build_rows(
        [change], (), (), [], change_risk.ChangeRiskWeights(), AGORA, Settings(), None, dep_findings
    )
    assert rows[0]["band"] == "alto"
    assert "dependência" in rows[0]["contributors_json"]
