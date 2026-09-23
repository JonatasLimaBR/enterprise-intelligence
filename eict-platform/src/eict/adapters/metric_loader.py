"""Carrega o registry de métricas do disco, no mesmo padrão dos contratos.

`registry.yaml` lista os arquivos que o extrator varre. Sem essa lista, "código que ninguém
declarou" seria indetectável por construção: só se procuraria onde já há declaração.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from eict.domain.metrics import MetricDeclaration, MetricError, parse_declaration

logger = logging.getLogger(__name__)

METRIC_GLOB = "*.yaml"
REGISTRY_FILE = "registry.yaml"


@dataclass(frozen=True)
class RegistryOutcome:
    declarations: tuple[MetricDeclaration, ...]
    sources: tuple[tuple[str, str], ...]
    errors: tuple[str, ...]

    @property
    def canonical(self) -> tuple[MetricDeclaration, ...]:
        return tuple(item for item in self.declarations if item.is_canonical)


def load_registry(directory: str | Path) -> RegistryOutcome:
    """Um arquivo inválido não impede os demais — mesma tolerância dos contratos."""
    base = Path(directory)
    if not base.exists():
        return RegistryOutcome((), (), (f"diretório de métricas não encontrado: {base}",))

    declarations: list[MetricDeclaration] = []
    errors: list[str] = []
    for path in sorted(base.glob(METRIC_GLOB)):
        if path.name == REGISTRY_FILE:
            continue
        try:
            declarations.append(load_file(path))
        except (MetricError, yaml.YAMLError, OSError) as exc:
            logger.warning("métrica %s recusada: %s", path.name, exc)
            errors.append(f"{path.name}: {exc}")

    sources, source_errors = _load_sources(base / REGISTRY_FILE)
    return RegistryOutcome(tuple(declarations), sources, tuple(errors + source_errors))


def load_file(path: str | Path) -> MetricDeclaration:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise MetricError(f"{path}: conteúdo não é um mapeamento")
    return parse_declaration(payload)


def _load_sources(path: Path) -> tuple[tuple[tuple[str, str], ...], list[str]]:
    """Pares (arquivo, ativo) que o extrator deve varrer."""
    if not path.exists():
        return (), [f"registry não encontrado: {path}"]
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        return (), [f"{path.name}: {exc}"]

    pares: list[tuple[str, str]] = []
    erros: list[str] = []
    for item in payload.get("sources", []) or []:
        caminho = (item or {}).get("path", "")
        ativo = (item or {}).get("asset", "")
        if caminho and ativo:
            pares.append((caminho, ativo))
        else:
            erros.append(f"{path.name}: entrada sem `path` ou `asset`: {item}")
    return tuple(pares), erros
