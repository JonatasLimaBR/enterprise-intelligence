"""Carrega as declarações de regime de baseline do disco, no padrão de contratos e métricas.

Uma declaração inválida é recusada inteira e as demais seguem: um arquivo quebrado não pode
apagar o regime de outro job.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from eict.domain.regimes import Regime, RegimeError, parse_declaration

logger = logging.getLogger(__name__)

REGIME_GLOB = "*.yaml"


@dataclass(frozen=True)
class RegimeOutcome:
    regimes: tuple[Regime, ...]
    errors: tuple[str, ...]


def load_directory(directory: str | Path) -> RegimeOutcome:
    base = Path(directory)
    if not base.exists():
        return RegimeOutcome((), ())
    regimes: list[Regime] = []
    errors: list[str] = []
    for path in sorted(base.glob(REGIME_GLOB)):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, dict):
                raise RegimeError(f"{path.name}: conteúdo não é um mapeamento")
            regimes.append(parse_declaration(payload, path.name))
        except (RegimeError, yaml.YAMLError, OSError) as exc:
            logger.warning("declaração de regime %s recusada: %s", path.name, exc)
            errors.append(f"{path.name}: {exc}")
    return RegimeOutcome(tuple(regimes), tuple(errors))
