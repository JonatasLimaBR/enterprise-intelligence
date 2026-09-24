"""Regime de baseline: a partir de quando os runs de um job valem como referência.

Regressão *é* mudança de regime vista antes de alguém julgá-la. Por isso o regime novo nunca
nasce sozinho: começa por aceite humano no console ou por declaração versionada. Recuperação
não cria marco — o job voltou ao que era.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from eict.domain.models import Run, stable_id

CONSOLE = "console"
DECLARED = "declared"
FORWARDED_HEADER = "forwarded_header"
REPOSITORY = "repository"


class RegimeError(ValueError):
    """Declaração ou aceite inválido: recusado inteiro, nada é gravado."""


@dataclass(frozen=True)
class Regime:
    regime_id: str
    job_id: str
    origin: str
    decided_by: str
    reason: str
    identity_source: str
    effective_from_at: datetime | None = None
    effective_from_sha: str = ""
    incident_id: str = ""
    created_at: datetime | None = None


def parse_declaration(payload: dict, source: str = "") -> Regime:
    """Declaração do repositório: `job_id`, `owner`, `reason` e exatamente um marco."""
    job_id = str(payload.get("job_id") or "").strip()
    owner = str(payload.get("owner") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    marco = payload.get("effective_from") or {}
    faltando = [nome for nome, valor in (("job_id", job_id), ("owner", owner), ("reason", reason)) if not valor]
    if faltando:
        raise RegimeError(f"{source}: campos obrigatórios ausentes: {', '.join(faltando)}")
    if not isinstance(marco, dict):
        raise RegimeError(f"{source}: effective_from deve ser um mapeamento")

    sha = str(marco.get("git_sha") or "").strip()
    instante = marco.get("at")
    if bool(sha) == bool(instante):
        raise RegimeError(f"{source}: effective_from exige exatamente um de git_sha ou at")
    if instante and not isinstance(instante, datetime):
        try:
            instante = datetime.fromisoformat(str(instante).replace("Z", "+00:00"))
        except ValueError as exc:
            raise RegimeError(f"{source}: effective_from.at inválido: {instante}") from exc

    return Regime(
        regime_id=stable_id("reg", job_id, DECLARED, sha or instante.isoformat()),
        job_id=job_id,
        origin=DECLARED,
        decided_by=owner,
        reason=reason,
        identity_source=REPOSITORY,
        effective_from_at=instante or None,
        effective_from_sha=sha,
    )


def regime_start(job_id: str, regimes: list[Regime], history: list[Run]) -> datetime | None:
    """Início do regime vigente: o marco mais recente que já se materializou.

    Marco por sha vale a partir do primeiro run daquele commit; sha sem run ainda é marco
    pendente — ignorado até aparecer, em vez de cortar a história num instante inventado.
    """
    inicios: list[datetime] = []
    for regime in regimes:
        if regime.job_id != job_id:
            continue
        if regime.effective_from_at is not None:
            inicios.append(regime.effective_from_at)
        elif regime.effective_from_sha:
            primeiro = _first_run_of_sha(job_id, regime.effective_from_sha, history)
            if primeiro is not None:
                inicios.append(primeiro)
    return max(inicios) if inicios else None


def _first_run_of_sha(job_id: str, sha: str, history: list[Run]) -> datetime | None:
    inicios = [
        run.start_time
        for run in history
        if run.job_id == job_id and run.git_sha and _same_sha(run.git_sha, sha)
    ]
    return min(inicios) if inicios else None


def _same_sha(a: str, b: str) -> bool:
    """Aceita sha abreviado na declaração, como em `git log --oneline`."""
    menor, maior = sorted((a.lower(), b.lower()), key=len)
    return len(menor) >= 7 and maior.startswith(menor)
