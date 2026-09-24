from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from eict.adapters.contract_loader import load_directory, load_file
from eict.domain.contracts import ContractError, parse_contract, summary_row

REPO_CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
NOW = datetime(2026, 9, 21, tzinfo=UTC)

VALIDO = {
    "contract_id": "workspace.eict_workload.orders",
    "version": "1.0.0",
    "status": "active",
    "owner": "dados@exemplo.com",
    "producer": "gerador",
    "asset": "workspace.eict_workload.orders",
    "consumers": ["painel"],
    "columns": [{"name": "order_id", "type": "string", "required": True}],
    "slo": {"freshness": "30m"},
    "quality": [
        {
            "rule_id": "orders_customer_id_not_null",
            "dimension": "completeness",
            "expression": "customer_id",
            "threshold": ">= 99.9%",
            "severity": "critical",
            "owner": "dados@exemplo.com",
        }
    ],
}


def escrever(base: Path, nome: str, payload: dict) -> Path:
    caminho = base / nome
    caminho.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return caminho


def test_at001_contrato_valido_e_carregado():
    contrato = parse_contract(VALIDO, "orders.yaml")

    assert contrato.contract_id == "workspace.eict_workload.orders"
    assert contrato.is_active is True
    assert contrato.quality[0].dimension == "completeness"
    assert contrato.quality[0].owner == "dados@exemplo.com"
    assert contrato.freshness_slo == "30m"


def test_at002_regra_sem_owner_e_rejeitada_apontando_o_arquivo():
    payload = {**VALIDO, "quality": [{**VALIDO["quality"][0], "owner": ""}]}

    with pytest.raises(ContractError) as exc:
        parse_contract(payload, "orders.yaml")

    assert "orders.yaml" in str(exc.value)
    assert "owner" in str(exc.value)


def test_regra_sem_severidade_valida_e_rejeitada():
    payload = {**VALIDO, "quality": [{**VALIDO["quality"][0], "severity": "urgentissimo"}]}

    with pytest.raises(ContractError, match="severidade inválida"):
        parse_contract(payload, "orders.yaml")


def test_dimensao_desconhecida_e_rejeitada():
    payload = {**VALIDO, "quality": [{**VALIDO["quality"][0], "dimension": "beleza"}]}

    with pytest.raises(ContractError, match="dimensão não suportada"):
        parse_contract(payload, "orders.yaml")


def test_contrato_sem_regras_e_rejeitado():
    payload = {**VALIDO, "quality": []}

    with pytest.raises(ContractError):
        parse_contract(payload, "orders.yaml")


def test_contrato_em_rascunho_nao_e_ativo():
    contrato = parse_contract({**VALIDO, "status": "proposed"}, "orders.yaml")

    assert contrato.is_active is False


def test_arquivo_invalido_nao_impede_os_demais(tmp_path: Path):
    escrever(tmp_path, "bom.yaml", VALIDO)
    escrever(tmp_path, "ruim.yaml", {**VALIDO, "quality": [{"rule_id": "x"}]})

    resultado = load_directory(tmp_path)

    assert [c.contract_id for c in resultado.contracts] == ["workspace.eict_workload.orders"]
    assert len(resultado.errors) == 1
    assert "ruim.yaml" in resultado.errors[0]


def test_diretorio_inexistente_vira_erro_explicito(tmp_path: Path):
    resultado = load_directory(tmp_path / "nao-existe")

    assert resultado.contracts == ()
    assert "não encontrado" in resultado.errors[0]


def test_yaml_malformado_aponta_o_arquivo(tmp_path: Path):
    (tmp_path / "quebrado.yaml").write_text("contract_id: [\n", encoding="utf-8")

    with pytest.raises(ContractError, match="quebrado.yaml"):
        load_file(tmp_path / "quebrado.yaml")


def test_resumo_para_persistencia():
    contrato = parse_contract(VALIDO, "orders.yaml")

    linha = summary_row(contrato, NOW)

    assert linha["rule_count"] == 1
    assert linha["declared_consumers"] == ["painel"]
    assert linha["loaded_at"] == NOW


def test_contratos_do_repositorio_sao_validos():
    resultado = load_directory(REPO_CONTRACTS)

    assert resultado.errors == ()
    assert len(resultado.active) == 4  # + sales_daily_small (demonstração do risco de SLA)
    assert all(rule.owner for contrato in resultado.contracts for rule in contrato.quality)


def test_sc10_toda_regra_do_repositorio_tem_dono_e_severidade():
    resultado = load_directory(REPO_CONTRACTS)

    for contrato in resultado.contracts:
        for regra in contrato.quality:
            assert regra.owner, f"{contrato.contract_id}/{regra.rule_id} sem owner"
            assert regra.severity, f"{contrato.contract_id}/{regra.rule_id} sem severidade"
