"""Carrega e valida `change_risk/weights.yaml`.

Fail-safe: arquivo ausente, YAML inválido ou valores fora do lugar ⇒ devolve os pesos-padrão
versionados. O score nunca deixa de ser calculado por causa da config.
"""

from __future__ import annotations

import logging
from dataclasses import fields
from pathlib import Path

import yaml

from eict.domain.change_risk import ChangeRiskWeights

logger = logging.getLogger(__name__)

FILENAME = "weights.yaml"
_TUPLE_FIELDS = {"author_patterns", "trailer_patterns"}


def load_weights(directory: str | Path) -> ChangeRiskWeights:
    if not directory:
        return ChangeRiskWeights()
    path = Path(directory)
    if path.is_dir():
        path = path / FILENAME
    if not path.exists():
        logger.info("config de change_risk não encontrada: %s; usando pesos-padrão", path)
        return ChangeRiskWeights()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("config de change_risk %s recusada: %s; usando pesos-padrão", path, exc)
        return ChangeRiskWeights()
    if not isinstance(raw, dict):
        logger.warning("config de change_risk %s não é um mapa; usando pesos-padrão", path)
        return ChangeRiskWeights()
    defaults = ChangeRiskWeights()
    values: dict = {}
    for field in fields(ChangeRiskWeights):
        if field.name not in raw:
            continue
        bruto = raw[field.name]
        try:
            if field.name in _TUPLE_FIELDS:
                values[field.name] = tuple(str(item).lower() for item in bruto)
            elif isinstance(getattr(defaults, field.name), int) and not isinstance(getattr(defaults, field.name), bool):
                values[field.name] = int(bruto)
            else:
                values[field.name] = float(bruto)
        except (TypeError, ValueError):
            logger.warning("change_risk: valor inválido para %s (%r); mantendo padrão", field.name, bruto)
    return ChangeRiskWeights(**values)
