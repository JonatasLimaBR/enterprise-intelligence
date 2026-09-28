"""Domínio da detecção de segredos: regex, entropia, máscara e só linhas adicionadas.

Segredos usados são SINTÉTICOS. Os testes asseguram que o miolo do valor nunca aparece no finding.
"""

from __future__ import annotations

from datetime import UTC, datetime

from eict.adapters.secret_patterns import DEFAULT_POLICY
from eict.domain.models import Change
from eict.domain.secret_scan import added_lines, mask, scan, shannon_bits

AGORA = datetime(2026, 9, 28, tzinfo=UTC)
AWS = "AKIA1234567890ABCD12"  # sintético


def make_change(patch: str, files=("app.py",)):
    return Change(sha="c1", repo="acme/eict", author="alice", committed_at=AGORA, message="x", files=files, patch=patch)


def test_added_lines_ignora_contexto_e_removidas():
    patch = "+++ b/app.py\n+ nova\n contexto\n- removida\n"
    assert added_lines(patch) == [" nova"]


def test_mask_esconde_o_miolo():
    assert mask(AWS, 4) == "AKIA***"
    assert "1234567890" not in mask(AWS, 4)


def test_shannon_alto_para_aleatorio_baixo_para_repetido():
    assert shannon_bits("aB3dEfGhIjKlMnOpQrStUvWx") >= 4.0
    assert shannon_bits("aaaaaaaaaaaaaaaaaaaaaaaa") < 1.0


def test_detecta_aws_com_masked():
    [finding] = scan(make_change(f'+ AWS_KEY = "{AWS}"'), DEFAULT_POLICY)
    assert finding.pattern_name == "aws_access_key"
    assert finding.severity == "alta"
    assert finding.masked == "AKIA***"
    assert AWS[4:] not in finding.masked


def test_detecta_private_key():
    achados = scan(make_change("+ -----BEGIN RSA PRIVATE KEY-----"), DEFAULT_POLICY)
    assert any(f.pattern_name == "private_key" and f.severity == "alta" for f in achados)


def test_detecta_databricks_token():
    achados = scan(make_change("+ token = " + "dapi" + "0" * 32), DEFAULT_POLICY)
    assert any(f.pattern_name == "databricks_token" for f in achados)


def test_detecta_generico():
    achados = scan(make_change('+ api_key = "s3cr3tvalue"'), DEFAULT_POLICY)
    assert any(f.pattern_name == "generic_secret" and f.severity == "média" for f in achados)


def test_alta_entropia_vira_finding_media():
    achados = scan(make_change("+ blob = aB3dEfGhIjKlMnOpQrStUvWx"), DEFAULT_POLICY)
    assert any(f.pattern_name == "high_entropy" and f.severity == "média" for f in achados)


def test_palavra_comum_longa_nao_e_finding():
    assert scan(make_change("+ documentation_configuration_manager = valor"), DEFAULT_POLICY) == []


def test_so_linhas_adicionadas_contam():
    assert scan(make_change(f'- AWS_KEY = "{AWS}"'), DEFAULT_POLICY) == []
    assert scan(make_change(f'  AWS_KEY = "{AWS}"'), DEFAULT_POLICY) == []


def test_deterministico():
    patch = f'+ AWS_KEY = "{AWS}"'
    assert scan(make_change(patch), DEFAULT_POLICY) == scan(make_change(patch), DEFAULT_POLICY)
