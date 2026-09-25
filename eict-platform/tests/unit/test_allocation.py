"""Alocação, precedência, conservação e reconciliação (AT-01…10, AT-15, SC1–SC5)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from eict.adapters.allocation_loader import load_directory
from eict.adapters.contract_loader import load_directory as load_contracts
from eict.domain.allocation import (
    APP,
    ARQUIVO_RECUSADO,
    DOMINIO,
    JOB,
    NAO_ALOCADO,
    PIPELINE,
    PLATAFORMA,
    REGRA_CONFLITO,
    WAREHOUSE,
    AllocationError,
    ContractOwner,
    PlatformPool,
    Totals,
    UsageLine,
    allocate,
    allocation_rows,
    build_rules,
    parse_domain,
    parse_platform,
    periods,
    reconcile,
    rule_rows,
    tolerance,
    totals,
)
from eict.jobs.finops import contract_pairs

ROOT = Path(__file__).resolve().parents[2]
AGORA = datetime(2026, 9, 25, 12, tzinfo=UTC)


def _dominio(fonte="comercial.yaml", jobs=("sales-daily",), dominio="comercial", **extra):
    payload = {
        "business_unit": "vendas",
        "domain": dominio,
        "owner": "dono@x",
        "products": [{"product": "painel", "jobs": list(jobs)}],
        **extra,
    }
    return parse_domain(payload, fonte)


PLATAFORMA_POOL = PlatformPool("plataforma-eict", "plataforma@x", ("eict-cycle",), ("eict-console",), "_platform.yaml")
CONTRATO = ("generate-data", ContractOwner("workspace.w.orders", "dados@x", "workspace.w.orders"))


def _job(nome, custo="10", run="r1", job_id=None):
    return UsageLine(JOB, job_id or f"id-{nome}", nome, run, "JOBS", Decimal("1"), Decimal(custo))


def _regras(dominios=None, contratos=(CONTRATO,), **extra):
    return build_rules(dominios if dominios is not None else [_dominio()], PLATAFORMA_POOL, contratos, **extra)


def test_at01_job_no_yaml_vai_para_o_dominio_com_motivo():
    [item] = allocate([_job("sales-daily")], _regras())
    assert (item.category, item.domain, item.product, item.business_unit) == (DOMINIO, "comercial", "painel", "vendas")
    assert item.reason == "regra de alocação (comercial.yaml)"
    assert item.owner == "dono@x"


def test_at01_nome_de_deploy_dev_casa_por_igualdade_normalizada():
    [item] = allocate([_job("[dev fulano] sales-daily-dev")], _regras())
    assert item.category == DOMINIO


def test_substring_nao_casa():
    [item] = allocate([_job("sales-daily-small")], _regras())
    assert item.category == NAO_ALOCADO


def test_at02_produtor_de_contrato_sem_yaml_vai_para_o_dono_do_contrato():
    [item] = allocate([_job("generate-data")], _regras())
    assert (item.category, item.owner, item.reason) == (DOMINIO, "dados@x", "contrato")


def test_at03_sc1_yaml_vence_o_contrato():
    contrato = ("sales-daily", ContractOwner("workspace.w.sales", "outro@x", "workspace.w.sales"))
    [item] = allocate([_job("sales-daily")], _regras(contratos=(contrato,)))
    assert item.owner == "dono@x"
    assert item.reason.startswith("regra de alocação")


def test_produtor_de_varios_contratos_escolhe_o_primeiro_e_cita_os_outros():
    contratos = (
        ("gen", ContractOwner("b.orders", "b@x", "b.orders")),
        ("gen", ContractOwner("a.customers", "a@x", "a.customers")),
    )
    [item] = allocate([_job("gen")], _regras(contratos=contratos))
    assert item.owner == "a@x"
    assert "b.orders" in item.reason


def test_at04_sc5_ciclo_app_pipeline_e_warehouse_da_plataforma_vao_para_o_pool():
    regras = _regras(platform_pipeline_id="pipe-1", platform_warehouse_id="wh-1")
    linhas = [
        _job("eict-cycle-dev"),
        UsageLine(APP, "app-1", "eict-console-dev", "", "APPS", Decimal("1"), Decimal("2")),
        UsageLine(PIPELINE, "pipe-1", "pipe-1", "", "DLT", Decimal("1"), Decimal("3")),
        UsageLine(WAREHOUSE, "wh-1", "wh-1", "", "SQL", Decimal("1"), Decimal("4")),
    ]
    assert {item.category for item in allocate(linhas, regras)} == {PLATAFORMA}


def test_pipeline_de_outro_id_nao_vai_para_o_pool():
    regras = _regras(platform_pipeline_id="pipe-1")
    [item] = allocate([UsageLine(PIPELINE, "pipe-9", "pipe-9", "", "DLT", Decimal("1"), Decimal("1"))], regras)
    assert item.category == NAO_ALOCADO
    assert "pipe-9" in item.reason


def test_at05_sc3_job_desconhecido_fica_nao_alocado_com_o_nome():
    [item] = allocate([_job("break-contract")], _regras())
    assert item.category == NAO_ALOCADO
    assert item.reason == "sem regra: break-contract"


def test_job_sem_nome_cita_o_id():
    [item] = allocate([_job("", job_id="777")], _regras())
    assert "777" in item.reason


def test_at06_uso_sem_recurso_identificavel():
    linha = UsageLine("", "", "", "", "MODEL_SERVING", Decimal("1"), Decimal("5"))
    [item] = allocate([linha], _regras())
    assert item.category == NAO_ALOCADO
    assert item.reason == "recurso não identificado (MODEL_SERVING)"


def test_at07_conflito_anula_so_o_job_disputado_e_nao_desce_para_o_contrato():
    a = _dominio("a.yaml", jobs=("generate-data", "job-a"))
    b = _dominio("b.yaml", jobs=("generate-data", "job-b"), dominio="outro")
    regras = _regras(dominios=[a, b])
    disputado, job_a, job_b = allocate([_job("generate-data"), _job("job-a"), _job("job-b")], regras)
    assert disputado.category == NAO_ALOCADO
    assert disputado.reason == "conflito entre a.yaml e b.yaml"
    assert (job_a.category, job_b.category) == (DOMINIO, DOMINIO)
    linhas = rule_rows([a, b], PLATAFORMA_POOL, regras, (), AGORA)
    conflitos = [row for row in linhas if row["status"] == REGRA_CONFLITO]
    assert {row["source_file"] for row in conflitos} == {"a.yaml", "b.yaml"}
    assert all(row["job_name"] == "generate-data" for row in conflitos)


def test_mesmo_job_duas_vezes_no_mesmo_arquivo_recusa_o_arquivo():
    with pytest.raises(AllocationError, match="mais de uma vez"):
        _dominio(jobs=("x", "[dev a] x-dev"))


def test_at08_sc2_conservacao_ao_centavo():
    linhas = [
        _job("sales-daily", "0.1"),
        _job("generate-data", "0.2"),
        _job("eict-cycle", "0.3"),
        _job("desconhecido", "0.0001"),
        UsageLine("", "", "", "", "X", Decimal("0"), Decimal("1234.5678")),
    ]
    alocacoes = allocate(linhas, _regras())
    assert len(alocacoes) == len(linhas)
    assert totals(alocacoes).total == sum(linha.cost for linha in linhas)
    assert sum(row["cost"] for row in allocation_rows(alocacoes)) == sum(linha.cost for linha in linhas)


def test_linhas_do_mesmo_recurso_se_agrupam():
    rows = allocation_rows(allocate([_job("sales-daily", "1", "r1"), _job("sales-daily", "2", "r2")], _regras()))
    assert len(rows) == 1
    assert rows[0]["cost"] == Decimal("3")


def test_at09_diferenca_de_0_4_por_cento_reconcilia():
    resultado = reconcile(Decimal("1000"), Totals(allocated=Decimal("996")))
    assert resultado.reconciled


def test_at10_sc4_tres_dolares_em_quinhentos_nao_reconcilia():
    resultado = reconcile(Decimal("500"), Totals(allocated=Decimal("497")))
    assert not resultado.reconciled
    assert "tolerância" in resultado.reason


def test_tolerancia_tem_piso_de_um_dolar():
    assert tolerance(Decimal("10")) == Decimal("1")
    assert reconcile(Decimal("10"), Totals(allocated=Decimal("9.2"))).reconciled


def test_mais_de_uma_moeda_nao_reconcilia():
    resultado = reconcile(Decimal("10"), Totals(allocated=Decimal("10")), ("USD", "EUR"))
    assert not resultado.reconciled
    assert "moeda" in resultado.reason


def test_g10_fracao_alocada_ignora_o_pool():
    assert Totals(Decimal("30"), Decimal("900"), Decimal("10")).allocated_share == pytest.approx(0.75)
    assert Totals(platform_pool=Decimal("5")).allocated_share is None


@pytest.mark.parametrize("campo", ["business_unit", "domain", "owner"])
def test_at15_yaml_sem_campo_obrigatorio_e_recusado(campo):
    payload = {"business_unit": "v", "domain": "d", "owner": "o", "products": [{"product": "p", "jobs": ["j"]}]}
    payload[campo] = ""
    with pytest.raises(AllocationError, match=campo):
        parse_domain(payload, "x.yaml")


def test_produto_sem_jobs_e_recusado():
    with pytest.raises(AllocationError, match="sem `jobs`"):
        parse_domain({"business_unit": "v", "domain": "d", "owner": "o", "products": [{"product": "p"}]}, "x.yaml")


def test_produto_herda_o_dono_do_dominio():
    assert _dominio().products[0].owner == "dono@x"


def test_plataforma_sem_dono_e_recusada():
    with pytest.raises(AllocationError, match="owner"):
        parse_platform({"pool": "p"}, "_platform.yaml")


def test_loader_recusa_so_o_arquivo_invalido(tmp_path):
    (tmp_path / "bom.yaml").write_text(
        "business_unit: v\ndomain: d\nowner: o\nproducts:\n  - product: p\n    jobs: [j]\n", encoding="utf-8"
    )
    (tmp_path / "sem_dono.yaml").write_text(
        "business_unit: v\ndomain: d\nproducts:\n  - product: p\n    jobs: [k]\n", encoding="utf-8"
    )
    (tmp_path / "_platform.yaml").write_text("pool: p\nowner: o\njobs: [eict-cycle]\n", encoding="utf-8")
    carga = load_directory(tmp_path)
    assert [item.source_file for item in carga.domains] == ["bom.yaml"]
    assert carga.platform is not None and carga.platform.jobs == ("eict-cycle",)
    assert [arquivo for arquivo, _ in carga.errors] == ["sem_dono.yaml"]
    linhas = rule_rows(carga.domains, carga.platform, build_rules(carga.domains, carga.platform), carga.errors, AGORA)
    assert [row["source_file"] for row in linhas if row["status"] == ARQUIVO_RECUSADO] == ["sem_dono.yaml"]


def test_periodos_em_utc_com_virada_de_ano():
    anterior, corrente = periods(datetime(2026, 1, 10, 5, tzinfo=UTC))
    assert (anterior.label, corrente.label) == ("2025-12", "2026-01")
    assert anterior.end == corrente.start == datetime(2026, 1, 1, tzinfo=UTC)
    assert corrente.current and not anterior.current


def test_repositorio_alocacao_real_da_demo():
    carga = load_directory(ROOT / "allocation")
    contratos = load_contracts(ROOT / "contracts").active
    assert carga.errors == ()
    regras = build_rules(carga.domains, carga.platform, contract_pairs(list(contratos)))
    por_nome = {
        linha.resource_name: item
        for linha, item in (
            (item.line, item)
            for item in allocate(
                [
                    _job("[dev jonatas] eict-demo-sales-daily-dev"),
                    _job("eict-demo-generate-data-dev"),
                    _job("eict-cycle-dev"),
                    _job("eict-demo-break-contract-dev"),
                ],
                regras,
            )
        )
    }
    assert por_nome["[dev jonatas] eict-demo-sales-daily-dev"].reason.startswith("regra de alocação")
    assert por_nome["eict-demo-generate-data-dev"].reason.startswith("contrato")
    assert por_nome["eict-cycle-dev"].category == PLATAFORMA
    assert por_nome["eict-demo-break-contract-dev"].category == NAO_ALOCADO
