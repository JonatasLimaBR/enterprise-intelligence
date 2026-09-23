"""Fecha o incidente quando a condição que o abriu deixou de existir.

A invariante que sustenta tudo: **ausência de avaliação nunca resolve**. Uma regra que não
rodou não é uma regra que passou. Sem isso, um ciclo em que a etapa de qualidade falha
fecharia todos os incidentes abertos de uma vez — trocando "a fila limpa" por "a fila mente".
"""

from __future__ import annotations

from datetime import datetime

from eict.domain.models import Incident, TimelineEntry

RESOLUTION_KIND = "auto_resolved"

Subject = tuple[str, str]


def resolvable(
    incidents: list[Incident],
    evaluated: frozenset[Subject],
    violating: frozenset[Subject],
    now: datetime,
) -> list[tuple[Incident, TimelineEntry]]:
    """Incidentes com prova corrente de que o problema passou.

    `evaluated` e `violating` são conjuntos de `(subject, type)`. Um incidente resolve se e
    somente se foi avaliado neste ciclo **e** não está entre os que violam.
    """
    saida: list[tuple[Incident, TimelineEntry]] = []
    for incident in incidents:
        chave = (incident.subject, incident.type)
        if not incident.is_active or chave not in evaluated or chave in violating:
            continue
        resolvido = incident.resolved_at(now)
        saida.append((resolvido, _entry(resolvido, now)))
    return saida


def subjects_of(pairs: list[tuple[str, str]]) -> frozenset[Subject]:
    return frozenset(pairs)


def _entry(incident: Incident, now: datetime) -> TimelineEntry:
    return TimelineEntry.create(
        incident_id=incident.incident_id,
        at=now,
        kind=RESOLUTION_KIND,
        summary=(
            f"resolvido automaticamente: {incident.subject} foi avaliado neste ciclo "
            "e nenhuma condição do incidente persiste"
        ),
    )
