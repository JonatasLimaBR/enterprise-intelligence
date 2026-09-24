"""Risco de SLA: prazos, folga e classe com os números do DEFINE (AT-01…09, AT-15)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from eict.domain.incidents import SLA_RISK
from eict.domain.models import Incident
from eict.domain.sla import (
    DELIVERY_TIME,
    EM_RISCO,
    ENTREGUE_A_TEMPO,
    ESTOUROU,
    FRESHNESS,
    INEVITAVEL,
    NO_PRAZO,
    SEM_BASE,
    SUPERSEDED,
    VIOLADO,
    assess,
    classify,
    daily_deadline,
    expected_duration,
    most_urgent,
    outcome,
    remaining,
    superseded,
    window_deadline,
)
from tests.conftest import JOB_ID, make_run

AGORA = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
MIN = 60.0
SLO_30 = {FRESHNESS: "30m"}
SLO_0730 = {DELIVERY_TIME: "07:30 America/Sao_Paulo"}


def _avaliar(escrita_ha_min, restante_min=6, rodando_desde=None, slo=SLO_30):
    ultima = AGORA - timedelta(minutes=escrita_ha_min)
    return assess("ativo", slo, ultima, [ultima], AGORA, restante_min * MIN, "job", rodando_desde)[0]


def test_at01_com_folga():
    item = _avaliar(5)

    assert item.klass == NO_PRAZO
    assert item.slack_s == 9 * MIN


def test_at02_em_risco():
    item = _avaliar(10)

    assert item.klass == EM_RISCO
    assert item.slack_s == 4 * MIN
    assert item.severity == "warning"


def test_at03_inevitavel_com_prazo_ainda_futuro():
    item = _avaliar(17)

    assert item.klass == INEVITAVEL
    assert item.slack_s == -3 * MIN
    assert item.deadline > AGORA
    assert item.severity == "high"


def test_at04_prazo_passou_e_violado():
    assert _avaliar(31).klass == VIOLADO


def test_prazo_passado_e_violado_mesmo_sem_base():
    ultima = AGORA - timedelta(minutes=45)

    assert assess("ativo", SLO_30, ultima, [ultima], AGORA, None)[0].klass == VIOLADO


def test_at05_rodando_desconta_o_decorrido():
    assert remaining(6 * MIN, AGORA - timedelta(minutes=4), AGORA) == 2 * MIN


def test_at06_rodando_alem_do_esperado_nao_fica_negativo():
    assert remaining(6 * MIN, AGORA - timedelta(minutes=9), AGORA) == 0


def test_sc3_produtor_rodando_nao_alarma():
    """Escrita há 10 min seria em_risco com o produtor parado; rodando há 4 min, não é."""
    parado = _avaliar(10)
    rodando = _avaliar(10, rodando_desde=AGORA - timedelta(minutes=4))

    assert parado.klass == EM_RISCO
    assert rodando.klass == NO_PRAZO
    assert "rodando desde" in rodando.producer_state


def test_at07_sem_baseline():
    historia = [replace(make_run(i, 200), execution_s=30.0, setup_s=150.0) for i in range(4)]

    assert expected_duration(historia, JOB_ID, None) is None
    ultima = AGORA - timedelta(minutes=10)
    assert assess("ativo", SLO_30, ultima, [ultima], AGORA, None)[0].klass == SEM_BASE


def test_duracao_esperada_soma_medianas_de_setup_e_execucao():
    pares = [(28, 150), (29, 125), (27, 285), (30, 140), (28, 160)]
    historia = [
        replace(make_run(i, 200), execution_s=float(e), setup_s=float(s)) for i, (e, s) in enumerate(pares)
    ]

    assert expected_duration(historia, JOB_ID, None) == 150 + 28


def test_at08_prazo_diario_antes_das_0730():
    agora = datetime(2026, 9, 24, 9, 0, tzinfo=UTC)          # 06:00 em São Paulo
    ontem_tarde = agora - timedelta(hours=20)

    prazo, estourou = daily_deadline("07:30 America/Sao_Paulo", agora, [ontem_tarde])

    assert prazo == datetime(2026, 9, 24, 10, 30, tzinfo=UTC)  # 07:30 BRT = 10:30 UTC
    assert not estourou


def test_at09_prazo_diario_depois_com_entrega_vai_para_amanha():
    agora = datetime(2026, 9, 24, 11, 0, tzinfo=UTC)          # 08:00 em São Paulo
    entrega = datetime(2026, 9, 24, 10, 10, tzinfo=UTC)       # 07:10 em São Paulo

    prazo, estourou = daily_deadline("07:30 America/Sao_Paulo", agora, [entrega])

    assert prazo == datetime(2026, 9, 25, 10, 30, tzinfo=UTC)
    assert not estourou


def test_entrega_atrasada_de_ontem_nao_conta_como_a_de_hoje():
    """Ontem às 10:00 BRT (atrasada): não é a entrega de hoje; às 06:00, o prazo é hoje."""
    agora = datetime(2026, 9, 24, 9, 0, tzinfo=UTC)
    atrasada_ontem = datetime(2026, 9, 23, 13, 0, tzinfo=UTC)

    prazo, estourou = daily_deadline("07:30 America/Sao_Paulo", agora, [atrasada_ontem])

    assert prazo == datetime(2026, 9, 24, 10, 30, tzinfo=UTC)
    assert not estourou


def test_escrita_depois_do_prazo_nao_e_entrega():
    agora = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)          # 09:00 BRT
    atrasada = datetime(2026, 9, 24, 11, 50, tzinfo=UTC)      # 08:50 BRT

    _, estourou = daily_deadline("07:30 America/Sao_Paulo", agora, [atrasada])

    assert estourou


def test_prazo_diario_depois_sem_entrega_estourou():
    agora = datetime(2026, 9, 24, 11, 0, tzinfo=UTC)
    ontem = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)          # antes do prazo de ontem

    prazo, estourou = daily_deadline("07:30 America/Sao_Paulo", agora, [ontem])

    assert estourou
    assert prazo == datetime(2026, 9, 24, 10, 30, tzinfo=UTC)


def test_entrega_antecipada_antes_do_prazo_move_para_amanha():
    agora = datetime(2026, 9, 24, 9, 0, tzinfo=UTC)
    madrugada = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)       # 05:00 BRT

    prazo, _ = daily_deadline("07:30 America/Sao_Paulo", agora, [madrugada])

    assert prazo == datetime(2026, 9, 25, 10, 30, tzinfo=UTC)


def test_dois_slos_vale_o_mais_urgente():
    """06:00 BRT, escrita às 05:50: a entrega diária está feita; a janela de 30m está em risco."""
    agora = datetime(2026, 9, 24, 9, 0, tzinfo=UTC)
    ultima = agora - timedelta(minutes=10)
    itens = assess("ativo", {**SLO_30, **SLO_0730}, ultima, [ultima], agora, 6 * MIN)

    assert {item.slo_kind for item in itens} == {FRESHNESS, DELIVERY_TIME}
    assert most_urgent(itens).klass == EM_RISCO


def test_tabela_d9_do_design():
    """Produtor de ~3 min (150 + 28): risco entre ~12 e ~17 min após o run."""

    def classe(apos_min):
        ultima = AGORA - timedelta(minutes=apos_min)
        return assess("ativo", SLO_30, ultima, [ultima], AGORA, 178.0)[0].klass

    assert classe(11) == NO_PRAZO
    assert classe(13) == EM_RISCO
    assert classe(18) == INEVITAVEL
    assert classe(31) == VIOLADO


def test_classify_nos_limites():
    prazo = AGORA + timedelta(minutes=20)

    assert classify(prazo, AGORA, 5 * MIN)[0] == EM_RISCO     # folga exatamente = margem
    assert classify(prazo, AGORA, 10 * MIN)[0] == INEVITAVEL  # folga exatamente 0


def test_at15_desfecho():
    prazo = AGORA + timedelta(minutes=20)

    assert outcome(AGORA, prazo, [AGORA + timedelta(minutes=5)]) == ENTREGUE_A_TEMPO
    assert outcome(AGORA, prazo, [AGORA - timedelta(minutes=5)]) == ESTOUROU
    assert outcome(AGORA, prazo, [prazo + timedelta(seconds=1)]) == ESTOUROU


def _risco(state="detected"):
    return Incident(
        incident_id="inc-sla", correlation_key="k", tenant_id="demo", subject="ativo", type=SLA_RISK,
        state=state, severity="warning", first_run_id="e", last_run_id="e", detected_at=AGORA,
        updated_at=AGORA,
    )


def test_d6_violacao_supera_o_risco_sem_fingir_recuperacao():
    fechados = superseded([_risco()], frozenset({"ativo"}), SLA_RISK, AGORA)

    assert [item.state for item, _ in fechados] == ["closed"]
    assert fechados[0][1].kind == SUPERSEDED


def test_superacao_ignora_outro_ativo_e_incidente_fechado():
    assert superseded([_risco()], frozenset({"outro"}), SLA_RISK, AGORA) == []
    assert superseded([_risco("recovered")], frozenset({"ativo"}), SLA_RISK, AGORA) == []


def test_janela():
    assert window_deadline(AGORA, "30m") == AGORA + timedelta(minutes=30)
    assert window_deadline(AGORA, "24h") == AGORA + timedelta(days=1)
