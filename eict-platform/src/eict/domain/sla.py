"""Risco de SLA de freshness: o produtor ainda consegue entregar antes do prazo?

Não há cadência para aprender — os produtores não têm agenda e toda escrita foi manual. A
previsão vem do prazo **declarado** no contrato e do tempo que o produtor **medidamente** leva:

    folga = prazo − agora − restante do produtor − latência do ciclo

A latência do ciclo entra porque o aviso só existe quando o ciclo roda: um aviso que só pode
chegar depois do prazo não é previsão.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from eict.domain.baseline import MIN_SAMPLES, WINDOW
from eict.domain.models import Incident, Run, TimelineEntry
from eict.domain.rules import parse_duration_seconds

LATENCIA_CICLO_S = 600.0
MARGEM_S = 300.0
POLICY_VERSION = "sla-risk-v1"

NO_PRAZO = "no_prazo"
EM_RISCO = "em_risco"
INEVITAVEL = "inevitavel"
VIOLADO = "violado"
SEM_BASE = "sem_base"
AT_RISK = frozenset({EM_RISCO, INEVITAVEL})
_GRAVIDADE = {SEM_BASE: 0, NO_PRAZO: 1, EM_RISCO: 2, INEVITAVEL: 3, VIOLADO: 4}

FRESHNESS = "freshness"
DELIVERY_TIME = "delivery_time"

ENTREGUE_A_TEMPO = "entregue_a_tempo"
ESTOUROU = "estourou"
SUPERSEDED = "superseded"


@dataclass(frozen=True)
class Assessment:
    asset: str
    slo_kind: str
    deadline: datetime | None
    klass: str
    remaining_s: float | None = None
    slack_s: float | None = None
    producer_job_id: str = ""
    producer_state: str = ""
    reason: str = ""

    @property
    def at_risk(self) -> bool:
        return self.klass in AT_RISK

    @property
    def severity(self) -> str:
        return "high" if self.klass == INEVITAVEL else "warning"


# --- prazos -------------------------------------------------------------------------------------


def window_deadline(last_write: datetime, freshness: str) -> datetime:
    """Janela deslizante: o dado precisa ser reescrito antes de envelhecer além do SLO."""
    return last_write + timedelta(seconds=parse_duration_seconds(freshness))


def daily_deadline(
    delivery_time: str, now: datetime, writes: list[datetime]
) -> tuple[datetime, bool]:
    """Próximo prazo diário e se o de hoje já estourou.

    "Entregue hoje" é escrita desde a **meia-noite local** até o prazo. Contar desde o prazo de
    ontem trataria uma entrega atrasada de ontem (às 10:00) como a entrega de hoje, e o prazo de
    hoje nunca seria verificado. Escrita depois do prazo não conta: é atraso, não entrega.
    """
    hoje, meia_noite = _today_deadline(delivery_time, now)
    amanha = hoje + timedelta(days=1)
    if now <= hoje:
        entregue = any(meia_noite <= escrita <= now for escrita in writes)
        return (amanha if entregue else hoje), False
    entregue = any(meia_noite <= escrita <= hoje for escrita in writes)
    return (amanha, False) if entregue else (hoje, True)


def _today_deadline(delivery_time: str, now: datetime) -> tuple[datetime, datetime]:
    """`"07:30 America/Sao_Paulo"` → (hoje às 07:30, meia-noite de hoje) naquele fuso, em UTC."""
    horario, _, fuso = delivery_time.strip().partition(" ")
    zona = ZoneInfo(fuso.strip() or "UTC")
    horas, minutos = (int(parte) for parte in horario.split(":"))
    local = now.astimezone(zona).date()
    prazo = datetime.combine(local, time(horas, minutos), tzinfo=zona).astimezone(now.tzinfo)
    meia_noite = datetime.combine(local, time(0, 0), tzinfo=zona).astimezone(now.tzinfo)
    return prazo, meia_noite


# --- produtor -----------------------------------------------------------------------------------


def expected_duration(history: list[Run], job_id: str, regime_start: datetime | None) -> float | None:
    """Mediana do setup + mediana da execução, no regime vigente. Menos de 5 runs: sem base.

    O setup entra aqui, ao contrário do baseline de regressão: para o prazo, o que importa é
    quando o dado chega, e a partida do ambiente faz parte da espera.
    """
    runs = [
        run
        for run in history
        if run.job_id == job_id
        and run.succeeded
        and run.execution_s is not None
        and (regime_start is None or run.start_time >= regime_start)
    ]
    runs = sorted(runs, key=lambda run: run.end_time)[-WINDOW:]
    if len(runs) < MIN_SAMPLES:
        return None
    setup = statistics.median(run.setup_s or 0.0 for run in runs)
    execucao = statistics.median(run.execution_s for run in runs)
    return float(setup + execucao)


def remaining(expected_s: float, active_since: datetime | None, now: datetime) -> float:
    """Produtor rodando: desconta o decorrido, sem ficar negativo."""
    if active_since is None:
        return expected_s
    return max(0.0, expected_s - (now - active_since).total_seconds())


# --- classe -------------------------------------------------------------------------------------


def classify(deadline: datetime, now: datetime, remaining_s: float) -> tuple[str, float]:
    if now > deadline:
        return VIOLADO, (deadline - now).total_seconds()
    folga = (deadline - now).total_seconds() - remaining_s - LATENCIA_CICLO_S
    if folga > MARGEM_S:
        return NO_PRAZO, folga
    return (EM_RISCO if folga > 0 else INEVITAVEL), folga


def assess(
    asset: str,
    slo: dict[str, str],
    last_write: datetime,
    writes: list[datetime],
    now: datetime,
    expected_s: float | None,
    producer_job_id: str = "",
    active_since: datetime | None = None,
    reason_without_base: str = "",
) -> list[Assessment]:
    """Uma avaliação por SLO declarado. Prazo passado é violação mesmo sem base do produtor."""
    estado = f"rodando desde {active_since:%H:%M} UTC" if active_since else "parado"
    prazos: list[tuple[str, datetime, bool]] = []
    if slo.get(FRESHNESS):
        prazo = window_deadline(last_write, slo[FRESHNESS])
        prazos.append((FRESHNESS, prazo, now > prazo))
    if slo.get(DELIVERY_TIME):
        prazo, estourou = daily_deadline(slo[DELIVERY_TIME], now, writes)
        prazos.append((DELIVERY_TIME, prazo, estourou))

    saida: list[Assessment] = []
    for tipo, prazo, estourou in prazos:
        if estourou:
            saida.append(Assessment(asset, tipo, prazo, VIOLADO, producer_job_id=producer_job_id,
                                    producer_state=estado, reason="prazo passou sem entrega"))
            continue
        if expected_s is None:
            saida.append(Assessment(asset, tipo, prazo, SEM_BASE, producer_job_id=producer_job_id,
                                    producer_state=estado,
                                    reason=reason_without_base or "produtor sem baseline no regime"))
            continue
        resto = remaining(expected_s, active_since, now)
        classe, folga = classify(prazo, now, resto)
        saida.append(Assessment(asset, tipo, prazo, classe, resto, folga, producer_job_id, estado))
    return saida


def most_urgent(assessments: list[Assessment]) -> Assessment | None:
    """Com dois SLOs no mesmo ativo, vale o pior; empate, o de menor folga."""
    if not assessments:
        return None
    return max(
        assessments,
        key=lambda item: (_GRAVIDADE[item.klass], -(item.slack_s if item.slack_s is not None else 0.0)),
    )


def summary(item: Assessment) -> str:
    if item.klass == SEM_BASE:
        return f"SLA de {item.slo_kind} em {item.asset} sem previsão: {item.reason}"
    minutos = (item.slack_s or 0.0) / 60
    return (
        f"SLA de {item.slo_kind} em {item.asset}: {item.klass}; prazo {item.deadline:%Y-%m-%d %H:%M} UTC, "
        f"folga {minutos:.1f} min; produtor {item.producer_state}, "
        f"precisa de {(item.remaining_s or 0) / 60:.1f} min (+{LATENCIA_CICLO_S / 60:.0f} min de ciclo)"
    )


# --- desfecho e superação -----------------------------------------------------------------------


def outcome(predicted_at: datetime, deadline: datetime, writes: list[datetime]) -> str:
    """Houve escrita entre a previsão e o prazo? É o que mede se o aviso acertou."""
    return ENTREGUE_A_TEMPO if any(predicted_at < escrita <= deadline for escrita in writes) else ESTOUROU


def superseded(
    incidents: list[Incident], violated_assets: frozenset[str], incident_type: str, now: datetime
) -> list[tuple[Incident, TimelineEntry]]:
    """Prazo passou sem entrega: o risco virou violação, e a violação de freshness assume.

    Fechar como `recovered` mentiria — nada se recuperou. Deixar aberto duplicaria a fila.
    """
    saida = []
    for incident in incidents:
        if incident.type != incident_type or not incident.is_active:
            continue
        if incident.subject not in violated_assets:
            continue
        fechado = replace(incident, state="closed", updated_at=now, version=incident.version + 1)
        saida.append(
            (
                fechado,
                TimelineEntry.create(
                    incident_id=incident.incident_id,
                    at=now,
                    kind=SUPERSEDED,
                    summary=f"prazo estourado sem entrega em {incident.subject}; a violação de freshness assume",
                ),
            )
        )
    return saida
