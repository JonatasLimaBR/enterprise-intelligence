"""A escada de severidade do sistema, em um lugar só.

Havia duas: `SEVERITY_ORDER` conhecia quatro palavras e incidentes de runtime usavam
`high`, que não estava nela — o `.get(severity, 0)` fazia `high` cair abaixo de
`warning`. Enquanto nada comparava incidentes dos dois tipos, ninguém percebia.

Contrato declara quatro (ver `contracts.SEVERITIES`); o sistema usa cinco.
"""

from __future__ import annotations

from collections.abc import Iterable

LADDER = ("info", "warning", "high", "critical", "blocking")
CEILING = "critical"
FLOOR = LADDER[0]


def rank_of(severity: str) -> int:
    """Severidade desconhecida fica no piso, nunca acima de algo conhecido."""
    return LADDER.index(severity) if severity in LADDER else 0


def highest(severities: Iterable[str]) -> str:
    return max(severities, key=rank_of, default=FLOOR)


def capped_at(severity: str, ceiling: str = CEILING) -> str:
    return severity if rank_of(severity) <= rank_of(ceiling) else ceiling


def is_at_or_above(severity: str, other: str) -> bool:
    return rank_of(severity) >= rank_of(other)
