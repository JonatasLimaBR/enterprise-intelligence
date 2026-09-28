"""Job secret_scan + integração no change_risk (piso 'alto' e contribuidores)."""

from __future__ import annotations

from datetime import UTC, datetime

from eict.adapters.secret_patterns import DEFAULT_POLICY
from eict.domain.change_risk import ChangeRisk, SubScore
from eict.domain.models import Change
from eict.jobs import change_risk, secret_scan

AGORA = datetime(2026, 9, 28, tzinfo=UTC)
AWS = "AKIA1234567890ABCD12"


def make_change(patch: str, sha="c1"):
    return Change(
        sha=sha, repo="acme/eict", author="alice", committed_at=AGORA,
        message="x", files=("app.py",), patch=patch,
    )


def _risk(band="baixo"):
    zero = SubScore(0.0, "-")
    return ChangeRisk("c1", 0.1, band, zero, zero, zero, zero, ("orders",))


def test_build_rows_grava_finding_mascarado():
    rows = secret_scan.build_rows([make_change(f'+ AWS_KEY = "{AWS}"')], DEFAULT_POLICY, AGORA)
    [linha] = rows
    assert linha["pattern_name"] == "aws_access_key"
    assert linha["severity"] == "alta"
    assert linha["masked"] == "AKIA***"
    assert AWS[4:] not in linha["masked"]


def test_patch_limpo_zero_findings():
    assert secret_scan.build_rows([make_change("+ def soma(a, b):\n+     return a + b")], DEFAULT_POLICY, AGORA) == []


def test_apply_secrets_alta_impoe_piso_alto():
    findings = [{"pattern_name": "aws_access_key", "severity": "alta"}]
    resultado = change_risk.apply_secrets(_risk("baixo"), findings)
    assert resultado.band == "alto"
    assert any("aws_access_key" in c for c in resultado.contributors)


def test_apply_secrets_media_nao_impoe_piso():
    findings = [{"pattern_name": "generic_secret", "severity": "média"}]
    resultado = change_risk.apply_secrets(_risk("baixo"), findings)
    assert resultado.band == "baixo"
    assert any("generic_secret" in c for c in resultado.contributors)


def test_apply_secrets_sem_findings_e_no_op():
    risco = _risk("médio")
    assert change_risk.apply_secrets(risco, []) is risco


def test_build_rows_do_change_risk_usa_findings():
    from eict.config import Settings

    change = make_change(f'+ AWS_KEY = "{AWS}"')
    findings_by_sha = {"c1": [{"pattern_name": "aws_access_key", "severity": "alta"}]}
    rows = change_risk.build_rows(
        [change], (), (), [], change_risk.ChangeRiskWeights(), AGORA, Settings(), findings_by_sha
    )
    assert rows[0]["band"] == "alto"
    assert "segredo" in rows[0]["contributors_json"]
