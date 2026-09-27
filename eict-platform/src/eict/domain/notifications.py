"""Notificação outbound: decide os eventos materiais do incidente e monta as mensagens.

Puro, sem I/O. O job `notify` enfileira o que sai daqui e envia pela Cloud API do WhatsApp.
Um evento vira mensagem uma única vez: a chave de dedup carrega o tipo do evento (e a nova
severidade, no escalonamento), e o `insert_missing` do outbox garante o "uma vez só".
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from eict.domain.models import ACTIVE_INCIDENT_STATES, Incident
from eict.domain.severity import is_at_or_above

PIERCE = frozenset({"critical", "blocking"})
EVENT_LABELS = {"aberto": "ABERTO", "escalou": "ESCALOU", "recuperado": "RECUPERADO"}
NO_EVIDENCE = "sem evidências resumidas"
MAX_EVIDENCE = 2


class NotificationError(RuntimeError):
    """A mensagem não pôde ser montada — o incidente não tem o mínimo para identificar."""


@dataclass(frozen=True)
class NotificationConfig:
    destination: str
    opt_in: bool
    threshold: str
    template_name: str
    phone_number_id: str = ""
    template_lang: str = "pt_BR"
    console_url: str = ""
    quiet_start: time = time(22, 0)
    quiet_end: time = time(7, 0)
    quiet_tz: str = "America/Sao_Paulo"
    lookback_hours: int = 24

    @property
    def usable(self) -> bool:
        return bool(self.destination) and self.opt_in and bool(self.template_name) and bool(self.phone_number_id)


@dataclass(frozen=True)
class NotificationMessage:
    dedup_key: str
    incident_id: str
    event: str
    severity: str
    variables: tuple[str, ...]
    send_after: datetime


def in_quiet_hours(now: datetime, cfg: NotificationConfig) -> bool:
    local = now.astimezone(ZoneInfo(cfg.quiet_tz)).time()
    if cfg.quiet_start <= cfg.quiet_end:
        return cfg.quiet_start <= local < cfg.quiet_end
    return local >= cfg.quiet_start or local < cfg.quiet_end


def send_after(now: datetime, severity: str, cfg: NotificationConfig) -> datetime:
    if severity in PIERCE or not in_quiet_hours(now, cfg):
        return now
    tz = ZoneInfo(cfg.quiet_tz)
    local = now.astimezone(tz)
    end = local.replace(hour=cfg.quiet_end.hour, minute=cfg.quiet_end.minute, second=0, microsecond=0)
    if local.time() >= cfg.quiet_end:
        end = end + timedelta(days=1)
    return end.astimezone(now.tzinfo)


def _within(moment: datetime, now: datetime, hours: int) -> bool:
    return moment >= now - timedelta(hours=hours)


def material_events(incident: Incident, cfg: NotificationConfig, now: datetime) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    if incident.state in ACTIVE_INCIDENT_STATES and _within(incident.detected_at, now, cfg.lookback_hours):
        events.append(("aberto", f"{incident.incident_id}|aberto"))
    if incident.escalated_from:
        events.append(("escalou", f"{incident.incident_id}|escalou|{incident.severity}"))
    if incident.state == "recovered" and _within(incident.updated_at, now, cfg.lookback_hours):
        events.append(("recuperado", f"{incident.incident_id}|recuperado"))
    return events


def render_variables(
    incident: Incident, event: str, evidence: Sequence[str], cfg: NotificationConfig
) -> tuple[str, ...]:
    if not incident.subject or not incident.type:
        raise NotificationError(f"incidente {incident.incident_id} sem subject/type; não identificável")
    resumo = " · ".join(evidence[:MAX_EVIDENCE]) if evidence else NO_EVIDENCE
    impacto = f"{incident.impact_score:.2f} ({len(incident.affected_assets)} ativos)"
    link = cfg.console_url or f"incidente {incident.incident_id}"
    return (
        f"{EVENT_LABELS.get(event, event)} · {incident.severity}",
        incident.type,
        incident.subject,
        impacto,
        resumo,
        link,
    )


def messages_for(
    incidents: Iterable[Incident],
    cfg: NotificationConfig,
    now: datetime,
    evidence_by_incident: Mapping[str, Sequence[str]],
) -> list[NotificationMessage]:
    out: list[NotificationMessage] = []
    if not cfg.usable:
        return out
    for incident in incidents:
        if not is_at_or_above(incident.severity, cfg.threshold):
            continue
        for event, dedup in material_events(incident, cfg, now):
            try:
                variables = render_variables(incident, event, evidence_by_incident.get(incident.incident_id, ()), cfg)
            except NotificationError:
                continue
            out.append(
                NotificationMessage(
                    dedup_key=dedup,
                    incident_id=incident.incident_id,
                    event=event,
                    severity=incident.severity,
                    variables=variables,
                    send_after=send_after(now, incident.severity, cfg),
                )
            )
    return out
