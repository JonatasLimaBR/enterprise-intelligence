"""Carrega `finops/savings.yaml`. Inválido ou ausente ⇒ defaults do código e o motivo, para o console."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from eict.domain.savings import Policy, SavingsConfigError, parse_policy

logger = logging.getLogger(__name__)


def load(path: str | Path) -> tuple[Policy, str]:
    alvo = Path(path)
    try:
        return parse_policy(yaml.safe_load(alvo.read_text(encoding="utf-8"))), ""
    except (SavingsConfigError, yaml.YAMLError, OSError) as exc:
        logger.warning("política de economia recusada (%s); usando defaults: %s", alvo.name, exc)
        return Policy(), f"{alvo.name}: {exc}"
