"""Auto-resolução — e, sobretudo, quando ela NÃO deve acontecer.

Três destes testes existem só para impedir que a fila feche cedo demais. Um incidente
fechado por engano some da vista de quem deveria agir; um incidente que sobra a mais só
incomoda. Os dois erros não têm o mesmo peso.
"""

from __future__ import annotations

from datetime import UTC, datetime

from eict.domain.models import Incident
from eict.domain.resolution import RESOLUTION_KIND, resolvable

NOW = datetime(2026, 9, 22, 18, tzinfo=UTC)
ORDERS = "workspace.eict_workload.orders"
SALES = "workspace.eict_workload.sales_daily"
VIOLATION = "contract_violation"


def incidente(subject=ORDERS, tipo=VIOLATION, state="detected") -> Incident:
    return Incident(
        incident_id=f"inc-{subject[-6:]}-{tipo[:4]}",
        correlation_key="k",
        tenant_id="demo",
        subject=subject,
        type=tipo,
        state=state,
        severity="warning",
        first_run_id="r1",
        last_run_id="r1",
        detected_at=NOW,
        updated_at=NOW,
    )


def test_at12_avaliado_e_sem_violacao_resolve():
    resolvidos = resolvable(
        [incidente()], frozenset({(ORDERS, VIOLATION)}), frozenset(), NOW
    )

    assert len(resolvidos) == 1
    incident, entry = resolvidos[0]
    assert incident.state == "recovered"
    assert not incident.is_active
    assert entry.kind == RESOLUTION_KIND


def test_at13_sem_avaliacao_corrente_nao_resolve():
    """A invariante central: regra que não rodou não é regra que passou."""
    resolvidos = resolvable([incidente()], frozenset(), frozenset(), NOW)

    assert resolvidos == []


def test_at14_ainda_violando_nao_resolve():
    resolvidos = resolvable(
        [incidente()],
        frozenset({(ORDERS, VIOLATION)}),
        frozenset({(ORDERS, VIOLATION)}),
        NOW,
    )

    assert resolvidos == []


def test_avaliacao_de_outro_ativo_nao_resolve_este():
    resolvidos = resolvable(
        [incidente(subject=ORDERS)], frozenset({(SALES, VIOLATION)}), frozenset(), NOW
    )

    assert resolvidos == []


def test_avaliacao_de_outro_tipo_no_mesmo_ativo_nao_resolve():
    """Violação de contrato resolvida não fecha a falha do motor de avaliação."""
    resolvidos = resolvable(
        [incidente(tipo="quality_engine_failure")],
        frozenset({(ORDERS, VIOLATION)}),
        frozenset(),
        NOW,
    )

    assert resolvidos == []


def test_incidente_ja_fechado_nao_e_tocado():
    resolvidos = resolvable(
        [incidente(state="recovered")], frozenset({(ORDERS, VIOLATION)}), frozenset(), NOW
    )

    assert resolvidos == []


def test_varios_incidentes_resolvem_independentemente():
    abertos = [incidente(subject=ORDERS), incidente(subject=SALES)]

    resolvidos = resolvable(
        abertos,
        frozenset({(ORDERS, VIOLATION), (SALES, VIOLATION)}),
        frozenset({(SALES, VIOLATION)}),
        NOW,
    )

    assert [item.subject for item, _ in resolvidos] == [ORDERS]


def test_a_resolucao_registra_o_motivo_e_o_instante():
    _, entry = resolvable([incidente()], frozenset({(ORDERS, VIOLATION)}), frozenset(), NOW)[0]

    assert entry.at == NOW
    assert "avaliado neste ciclo" in entry.summary
    assert ORDERS in entry.summary


def test_versao_do_incidente_avanca_na_resolucao():
    incident, _ = resolvable([incidente()], frozenset({(ORDERS, VIOLATION)}), frozenset(), NOW)[0]

    assert incident.version == 2


def test_lista_vazia_nao_quebra():
    assert resolvable([], frozenset(), frozenset(), NOW) == []
