"""Qual job produz um ativo: o `producer` do contrato contra os jobs monitorados.

Por igualdade de nome normalizado, nunca por substring. `eict-demo-sales-daily` é substring de
`eict-demo-sales-daily-small`: casar por substring fazia o estado do produtor do painel
comercial vir dos runs do job pequeno.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PREFIXO_DEV = re.compile(r"^\[[^\]]+\]\s*")
_SUFIXO_TARGET = re.compile(r"-(dev|staging|prod)$")


@dataclass(frozen=True)
class MonitoredJob:
    job_id: str
    name: str
    active_run_id: str = ""
    active_since: object = None   # datetime | None — sem import para manter o módulo trivial

    @property
    def normalized_name(self) -> str:
        return normalize(self.name)


@dataclass(frozen=True)
class Resolution:
    job: MonitoredJob | None
    reason: str = ""


def normalize(name: str) -> str:
    """Tira o prefixo do modo development (`[dev fulano] `) e o sufixo do target."""
    return _SUFIXO_TARGET.sub("", _PREFIXO_DEV.sub("", (name or "").strip())).strip().lower()


def resolve(producer: str, jobs: list[MonitoredJob]) -> Resolution:
    alvo = normalize(producer)
    if not alvo:
        return Resolution(None, "contrato sem produtor")
    casados = [job for job in jobs if job.normalized_name == alvo]
    if not casados:
        return Resolution(None, f"produtor {producer} não está entre os jobs monitorados")
    if len(casados) > 1:
        ids = ", ".join(sorted(job.job_id for job in casados))
        return Resolution(None, f"produtor {producer} ambíguo: {ids}")
    return Resolution(casados[0])
