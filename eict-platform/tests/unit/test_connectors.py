"""Saúde dos conectores (AT-01…12)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eict.domain.connectors import (
    BACKOFF_MAX,
    DEGRADADO,
    FALHANDO,
    PERMANENTE,
    QUARANTINED,
    RESOLVED,
    RETRYING,
    SAUDAVEL,
    SEM_DADOS,
    TRANSITORIO,
    backoff,
    classify,
    health,
    record_failure,
    record_success,
    should_try,
)

AGORA = datetime(2026, 9, 24, 21, tzinfo=UTC)
SHA = "090e7938cd40d33bfb067a1e63e1a827b6d89a47"


def _falha(existente, status, quando=AGORA):
    return record_failure(existente, f"github-{SHA}", "github", SHA, f"github {status}", status, quando)


def test_classificacao():
    assert classify(422) == PERMANENTE
    assert classify(404) == PERMANENTE
    assert classify(503) == TRANSITORIO
    assert classify(429) == TRANSITORIO
    assert classify(None) == TRANSITORIO


def test_at01_422_vai_direto_para_a_quarentena():
    """O caso real: commit inexistente, retentado 7 vezes em 3 dias."""
    entrada = _falha(None, 422)

    assert entrada.status == QUARANTINED
    assert entrada.error_class == PERMANENTE
    assert entrada.attempts == 1
    assert entrada.next_attempt_at is None


def test_at02_transitorio_agenda_em_5_min():
    entrada = _falha(None, 503)

    assert entrada.status == RETRYING
    assert entrada.next_attempt_at == AGORA + timedelta(minutes=5)


def test_at03_terceira_falha_espera_20_min():
    entrada = _falha(_falha(_falha(None, 503), 503), 503)

    assert entrada.attempts == 3
    assert entrada.next_attempt_at == AGORA + timedelta(minutes=20)


def test_at04_backoff_tem_teto():
    assert backoff(20) == BACKOFF_MAX


def test_at05_quinta_falha_transitoria_vai_para_a_quarentena():
    entrada = None
    for _ in range(5):
        entrada = _falha(entrada, 503)

    assert entrada.status == QUARANTINED
    assert entrada.attempts == 5


def test_at06_quarentena_nao_e_retentada():
    assert not should_try(_falha(None, 422), AGORA + timedelta(days=30))


def test_at07_retentativa_antes_da_hora_nao_acontece():
    entrada = _falha(None, 503)

    assert not should_try(entrada, AGORA + timedelta(minutes=4))
    assert should_try(entrada, AGORA + timedelta(minutes=5))


def test_at08_fonte_voltou_fecha_a_mensagem():
    resolvida = record_success(_falha(None, 503), AGORA + timedelta(minutes=6))

    assert resolvida.status == RESOLVED
    assert resolvida.attempts == 1
    assert should_try(resolvida, AGORA)


def test_at09_mesma_mensagem_uma_linha_so():
    primeira = _falha(None, 503, AGORA)
    segunda = _falha(primeira, 503, AGORA + timedelta(minutes=5))

    assert segunda.dlq_id == primeira.dlq_id
    assert segunda.attempts == 2
    assert segunda.first_at == AGORA


def test_nunca_vista_e_tentada():
    assert should_try(None, AGORA)


def test_at10_quarentena_deixa_o_conector_degradado():
    saude = health("github", AGORA - timedelta(hours=1), None, [_falha(None, 422)], AGORA)

    assert saude.status == DEGRADADO
    assert saude.quarantined == 1


def test_at11_sem_sucesso_ha_25h_com_erro_esta_falhando():
    saude = health("github", AGORA - timedelta(hours=25), "github 503", [], AGORA)

    assert saude.status == FALHANDO
    assert "há 25 h" in saude.detail


def test_nunca_teve_sucesso_e_tem_erro_esta_falhando():
    assert health("github", None, "github 401", [], AGORA).status == FALHANDO


def test_at12_saudavel():
    saude = health("github", AGORA - timedelta(minutes=5), None, [], AGORA)

    assert saude.status == SAUDAVEL


def test_resolvidas_nao_contam():
    resolvida = record_success(_falha(None, 503), AGORA)

    assert health("github", AGORA, None, [resolvida], AGORA).status == SAUDAVEL


def test_sem_dados():
    assert health("github", None, None, [], AGORA).status == SEM_DADOS
