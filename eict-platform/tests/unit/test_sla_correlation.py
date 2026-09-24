"""Risco de SLA no correlator: abre, piora, fecha quando o dado chega, é superado quando estoura."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from eict.adapters.databricks_jobs import MonitoredJob as JobDoAdapter
from eict.adapters.databricks_jobs import active_run
from eict.domain.incidents import SLA_RISK
from eict.domain.producers import MonitoredJob
from eict.domain.sla import EM_RISCO, FRESHNESS, INEVITAVEL, NO_PRAZO, SEM_BASE, VIOLADO, Assessment
from eict.jobs.correlate import states_by_producer
from eict.jobs.correlate_quality import QualityInput, correlate_quality
from eict.jobs.sla_risk import most_urgent_per_asset

AGORA = datetime(2026, 9, 24, 12, tzinfo=UTC)
TENANT = "demo"
ATIVO = "workspace.eict_workload.sales_daily_small"


def _item(klass, prazo_min=20, folga_min=4.0, ativo=ATIVO):
    return Assessment(
        asset=ativo,
        slo_kind=FRESHNESS,
        deadline=AGORA + timedelta(minutes=prazo_min),
        klass=klass,
        remaining_s=178.0,
        slack_s=folga_min * 60,
        producer_job_id="65105666981331",
        producer_state="parado",
    )


def _ciclo(itens, abertos=()):
    payload = QualityInput(results=[], contracts={}, changes=[], producer_states={}, sla=tuple(itens))
    return correlate_quality(payload, list(abertos), TENANT, AGORA)


def test_em_risco_abre_sla_risk_com_evidencia():
    touched, entries, evidences, _ = _ciclo([_item(EM_RISCO)])

    assert [(item.type, item.subject, item.severity) for item in touched] == [(SLA_RISK, ATIVO, "warning")]
    assert entries[0].kind == "detected"
    assert "em_risco" in evidences[0][1].summary
    assert "folga 4.0 min" in evidences[0][1].summary


def test_no_prazo_nao_abre_nada():
    assert _ciclo([_item(NO_PRAZO, folga_min=9)])[0] == []


def test_sem_base_nao_abre_nem_fecha():
    abertos = _ciclo([_item(EM_RISCO)])[0]

    assert _ciclo([_item(SEM_BASE)], abertos)[0] == []


def test_piora_para_inevitavel_eleva_a_severidade():
    abertos = _ciclo([_item(EM_RISCO)])[0]

    touched, _, _, _ = _ciclo([_item(INEVITAVEL, folga_min=-3)], abertos)

    assert touched[0].incident_id == abertos[0].incident_id
    assert touched[0].severity == "high"


def test_at12_dado_chegou_fecha_como_recovered():
    """Escrita nova move o prazo: a classe volta a no_prazo e a resolução existente fecha."""
    abertos = _ciclo([_item(EM_RISCO)])[0]

    touched, entries, _, _ = _ciclo([_item(NO_PRAZO, prazo_min=30, folga_min=17)], abertos)

    assert [item.state for item in touched] == ["recovered"]
    assert any(entry.kind == "auto_resolved" for entry in entries)


def test_at13_sem_escrita_nova_continua_aberto():
    abertos = _ciclo([_item(EM_RISCO)])[0]

    touched, _, _, _ = _ciclo([_item(EM_RISCO, prazo_min=15, folga_min=0.5)], abertos)

    assert all(item.state == "detected" for item in touched)


def test_prazo_estourado_supera_sem_fingir_recuperacao():
    abertos = _ciclo([_item(INEVITAVEL, folga_min=-3)])[0]

    touched, entries, _, _ = _ciclo([_item(VIOLADO, prazo_min=-1, folga_min=-1)], abertos)

    assert [item.state for item in touched] == ["closed"]
    assert [entry.kind for entry in entries] == ["superseded"]


def test_violado_sem_risco_aberto_nao_cria_nada():
    assert _ciclo([_item(VIOLADO, prazo_min=-1, folga_min=-1)])[0] == []


def test_mais_urgente_por_ativo():
    itens = [_item(NO_PRAZO, folga_min=9), _item(EM_RISCO), _item(NO_PRAZO, ativo="outro", folga_min=9)]

    escolhidos = {item.asset: item.klass for item in most_urgent_per_asset(itens)}

    assert escolhidos == {ATIVO: EM_RISCO, "outro": NO_PRAZO}


def test_g10_estado_do_produtor_nao_vem_do_job_pequeno():
    """O bug do substring: o produtor do painel herdava o estado do job pequeno."""
    jobs = [
        MonitoredJob("580618456320695", "[dev x] eict-demo-sales-daily-dev"),
        MonitoredJob("65105666981331", "[dev x] eict-demo-sales-daily-small-dev"),
    ]
    registros = [{"job_id": "65105666981331", "estado": "SUCCESS"}]

    estados = states_by_producer({"eict-demo-sales-daily", "eict-demo-sales-daily-small"}, jobs, registros)

    assert estados == {"eict-demo-sales-daily": False, "eict-demo-sales-daily-small": True}


def test_produtor_nao_resolvido_fica_de_fora():
    assert states_by_producer({"inexistente"}, [], []) == {}


def test_at16_run_ativo_e_visivel():
    inicio_ms = int(AGORA.timestamp() * 1000)

    class _Jobs:
        def list_runs(self, **kwargs):
            assert kwargs["active_only"] is True
            return [SimpleNamespace(run_id=42, start_time=inicio_ms)]

    ativo = active_run(SimpleNamespace(jobs=_Jobs()), JobDoAdapter("65105666981331", "pequeno", "env"))

    assert ativo == ("42", AGORA)


def test_sem_run_ativo_e_parado():
    class _Jobs:
        def list_runs(self, **kwargs):
            return []

    assert active_run(SimpleNamespace(jobs=_Jobs()), JobDoAdapter("1", "x", "env")) is None
