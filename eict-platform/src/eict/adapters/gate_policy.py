"""Carrega a policy de gate. Fail-safe conservador: inválida/ausente → `DEFAULT_POLICY` embutida
(segredo/dep alta = bloqueado, band alto = requer_aprovacao, resto = permite)."""

from __future__ import annotations

import logging
from dataclasses import fields
from pathlib import Path

import yaml

from eict.domain.gates import GatePolicy

logger = logging.getLogger(__name__)

FILENAME = "policy.yaml"
DEFAULT_POLICY = GatePolicy()
_VALID = {"permite", "requer_aprovacao", "bloqueado"}


def load_policy(directory: str | Path) -> GatePolicy:
    if not directory:
        return DEFAULT_POLICY
    path = Path(directory)
    if path.is_dir():
        path = path / FILENAME
    if not path.exists():
        return DEFAULT_POLICY
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("policy de gate %s recusada: %s; usando padrão", path, exc)
        return DEFAULT_POLICY
    outcomes = raw.get("outcomes") if isinstance(raw, dict) else None
    if not isinstance(outcomes, dict):
        return DEFAULT_POLICY
    values = {}
    for field in fields(GatePolicy):
        bruto = outcomes.get(field.name)
        if isinstance(bruto, str) and bruto in _VALID:
            values[field.name] = bruto
    return GatePolicy(**values)
