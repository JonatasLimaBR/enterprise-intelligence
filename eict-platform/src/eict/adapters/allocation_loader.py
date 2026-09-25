"""Carrega `allocation/*.yaml`: um arquivo por domínio e `_platform.yaml` para o pool.

Um arquivo inválido é recusado inteiro e os demais seguem — o padrão de contratos, regimes e
runbooks. O erro volta com o nome do arquivo, para aparecer no console.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from eict.domain.allocation import AllocationError, DomainFile, PlatformPool, parse_domain, parse_platform

logger = logging.getLogger(__name__)

PLATFORM_FILE = "_platform.yaml"


@dataclass(frozen=True)
class AllocationOutcome:
    domains: tuple[DomainFile, ...]
    platform: PlatformPool | None
    errors: tuple[tuple[str, str], ...]


def load_directory(directory: str | Path) -> AllocationOutcome:
    base = Path(directory)
    if not base.exists():
        return AllocationOutcome((), None, ((str(base), "diretório de alocação não encontrado"),))
    domains: list[DomainFile] = []
    platform: PlatformPool | None = None
    errors: list[tuple[str, str]] = []
    for path in sorted(base.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            if path.name == PLATFORM_FILE:
                platform = parse_platform(payload, path.name)
            else:
                domains.append(parse_domain(payload, path.name))
        except (AllocationError, yaml.YAMLError, OSError) as exc:
            logger.warning("alocação %s recusada: %s", path.name, exc)
            errors.append((path.name, str(exc)))
    return AllocationOutcome(tuple(domains), platform, tuple(errors))
