"""Produtor por nome normalizado exato (AT-10, AT-11)."""

from __future__ import annotations

from eict.domain.producers import MonitoredJob, normalize, resolve

GRANDE = MonitoredJob("580618456320695", "[dev creatorhubmedia01] eict-demo-sales-daily-dev")
PEQUENO = MonitoredJob("65105666981331", "[dev creatorhubmedia01] eict-demo-sales-daily-small-dev")


def test_normaliza_prefixo_dev_e_sufixo_de_target():
    assert normalize(GRANDE.name) == "eict-demo-sales-daily"
    assert normalize("eict-demo-sales-daily-prod") == "eict-demo-sales-daily"
    assert normalize("eict-demo-sales-daily") == "eict-demo-sales-daily"


def test_at10_substring_nao_casa():
    """O bug antigo: o produtor do painel casava com o job pequeno."""
    assert resolve("eict-demo-sales-daily", [PEQUENO, GRANDE]).job.job_id == "580618456320695"
    assert resolve("eict-demo-sales-daily-small", [PEQUENO, GRANDE]).job.job_id == "65105666981331"


def test_at11_ambiguo_nao_escolhe():
    gemeo = MonitoredJob("999", "eict-demo-sales-daily-prod")

    resolucao = resolve("eict-demo-sales-daily", [GRANDE, gemeo])

    assert resolucao.job is None
    assert "ambíguo" in resolucao.reason


def test_ausente_explica():
    resolucao = resolve("eict-demo-generate-data", [GRANDE])

    assert resolucao.job is None
    assert "não está entre os jobs monitorados" in resolucao.reason


def test_contrato_sem_produtor():
    assert resolve("", [GRANDE]).reason == "contrato sem produtor"
