"""Saúde dos conectores: quando retentar, quando desistir, e como mostrar que algo vai mal.

O caso que motivou: um commit que não existe no repositório foi buscado 7 vezes em 3 dias, sempre
com 422, sem que ninguém visse. Erro permanente não melhora com retentativa — vai para a
quarentena na primeira vez. Erro transitório ganha backoff exponencial e, se persistir, também.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

PERMANENTE = "permanente"
TRANSITORIO = "transitorio"

RETRYING = "retrying"
QUARANTINED = "quarantined"
RESOLVED = "resolved"

BACKOFF_BASE = timedelta(minutes=5)
BACKOFF_MAX = timedelta(hours=6)
MAX_ATTEMPTS = 5

SAUDAVEL = "saudavel"
DEGRADADO = "degradado"
FALHANDO = "falhando"
SEM_DADOS = "sem_dados"
STALE_AFTER = timedelta(hours=24)

_TRANSITORIOS_4XX = frozenset({408, 429})


def classify(status: int | None) -> str:
    """Sem status (rede, timeout) ou 5xx/408/429: pode passar. Demais 4xx: não vai passar."""
    if status is None or status >= 500 or status in _TRANSITORIOS_4XX:
        return TRANSITORIO
    return PERMANENTE


def backoff(attempts: int) -> timedelta:
    """5 min, 10, 20, 40… com teto de 6 h. `attempts` é o número de falhas já registradas."""
    atraso = BACKOFF_BASE * (2 ** max(attempts - 1, 0))
    return min(atraso, BACKOFF_MAX)


@dataclass(frozen=True)
class DlqEntry:
    dlq_id: str
    source: str
    payload: str
    error: str
    error_class: str
    attempts: int
    first_at: datetime
    at: datetime
    next_attempt_at: datetime | None
    status: str

    @property
    def is_open(self) -> bool:
        return self.status != RESOLVED


def record_failure(
    existing: DlqEntry | None,
    dlq_id: str,
    source: str,
    payload: str,
    error: str,
    status_code: int | None,
    now: datetime,
) -> DlqEntry:
    """Uma linha por mensagem: a falha nova atualiza a existente em vez de duplicar."""
    classe = classify(status_code)
    tentativas = (existing.attempts if existing else 0) + 1
    quarentena = classe == PERMANENTE or tentativas >= MAX_ATTEMPTS
    return DlqEntry(
        dlq_id=dlq_id,
        source=source,
        payload=payload,
        error=error[:500],
        error_class=classe,
        attempts=tentativas,
        first_at=existing.first_at if existing else now,
        at=now,
        next_attempt_at=None if quarentena else now + backoff(tentativas),
        status=QUARANTINED if quarentena else RETRYING,
    )


def record_success(existing: DlqEntry, now: datetime) -> DlqEntry:
    """A fonte voltou: a mensagem fecha, com a história preservada."""
    return replace(existing, status=RESOLVED, at=now, next_attempt_at=None)


def should_try(existing: DlqEntry | None, now: datetime) -> bool:
    """Nunca vista, resolvida, ou em retentativa já vencida. Quarentena não se tenta sozinha."""
    if existing is None or existing.status == RESOLVED:
        return True
    if existing.status == QUARANTINED:
        return False
    return existing.next_attempt_at is None or existing.next_attempt_at <= now


@dataclass(frozen=True)
class Health:
    connector: str
    status: str
    retrying: int
    quarantined: int
    last_success_at: datetime | None
    last_error: str
    detail: str


def health(
    connector: str,
    last_success_at: datetime | None,
    last_error: str | None,
    entries: list[DlqEntry],
    now: datetime,
) -> Health:
    abertas = [entry for entry in entries if entry.is_open]
    retrying = sum(1 for entry in abertas if entry.status == RETRYING)
    quarentena = sum(1 for entry in abertas if entry.status == QUARANTINED)
    erro = last_error or ""

    if last_success_at is None and not erro and not abertas:
        status, detalhe = SEM_DADOS, "nenhuma execução registrada"
    elif erro and (last_success_at is None or now - last_success_at > STALE_AFTER):
        idade = "nunca" if last_success_at is None else f"há {(now - last_success_at).total_seconds() / 3600:.0f} h"
        status, detalhe = FALHANDO, f"último sucesso {idade}; erro: {erro[:120]}"
    elif abertas:
        status, detalhe = DEGRADADO, f"{retrying} em retentativa, {quarentena} em quarentena"
    else:
        status, detalhe = SAUDAVEL, "sem falhas pendentes"
    return Health(connector, status, retrying, quarentena, last_success_at, erro, detalhe)
