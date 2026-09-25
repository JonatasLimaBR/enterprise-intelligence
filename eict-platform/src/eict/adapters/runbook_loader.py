"""Carrega os runbooks versionados do disco, no padrão de contratos e regimes.

Um arquivo inválido é recusado inteiro e os demais seguem: um runbook quebrado não pode esconder
os outros do plantonista.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from eict.domain.runbooks import Runbook, RunbookError, parse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunbookOutcome:
    runbooks: tuple[Runbook, ...]
    errors: tuple[str, ...]


def load_directory(directory: str | Path) -> RunbookOutcome:
    base = Path(directory)
    if not base.exists():
        return RunbookOutcome((), (f"diretório de runbooks não encontrado: {base}",))
    runbooks: list[Runbook] = []
    errors: list[str] = []
    for path in sorted(base.glob("*.yaml")):
        try:
            runbooks.append(parse(yaml.safe_load(path.read_text(encoding="utf-8")), path.name))
        except (RunbookError, yaml.YAMLError, OSError) as exc:
            logger.warning("runbook %s recusado: %s", path.name, exc)
            errors.append(str(exc))
    ids = [item.runbook_id for item in runbooks]
    duplicados = sorted({item for item in ids if ids.count(item) > 1})
    if duplicados:
        errors.append(f"runbook_id repetido: {', '.join(duplicados)}")
        runbooks = [item for item in runbooks if item.runbook_id not in duplicados]
    return RunbookOutcome(tuple(runbooks), tuple(errors))
