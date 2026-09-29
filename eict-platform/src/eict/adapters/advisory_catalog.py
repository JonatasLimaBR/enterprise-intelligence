"""Carrega o catálogo de advisories de supply chain.

Fail-safe que **continua avaliando**: catálogo inválido/ausente ⇒ `DEFAULT_ADVISORIES` embutido.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from eict.domain.supply_chain import Advisory

logger = logging.getLogger(__name__)

FILENAME = "advisories.yaml"

DEFAULT_ADVISORIES = (
    Advisory("pyyaml", "5.4", "alta", "CVE-2020-14343", "PyYAML full_load RCE (exemplo)"),
    Advisory("requests", "2.31.0", "média", "CVE-2023-32681", "requests vaza credencial em proxy (exemplo)"),
)


def _group(advisories: tuple[Advisory, ...]) -> dict[str, tuple[Advisory, ...]]:
    agrupado: dict[str, list[Advisory]] = {}
    for advisory in advisories:
        agrupado.setdefault(advisory.package.lower(), []).append(advisory)
    return {pacote: tuple(itens) for pacote, itens in agrupado.items()}


def load_advisories(directory: str | Path) -> dict[str, tuple[Advisory, ...]]:
    if not directory:
        return _group(DEFAULT_ADVISORIES)
    path = Path(directory)
    if path.is_dir():
        path = path / FILENAME
    if not path.exists():
        logger.info("catálogo de advisories não encontrado: %s; usando embutido", path)
        return _group(DEFAULT_ADVISORIES)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("catálogo de advisories %s recusado: %s; usando embutido", path, exc)
        return _group(DEFAULT_ADVISORIES)
    itens = _parse(raw.get("advisories") if isinstance(raw, dict) else None)
    if not itens:
        logger.warning("catálogo de advisories %s sem entradas válidas; usando embutido", path)
        return _group(DEFAULT_ADVISORIES)
    return _group(itens)


def _parse(items: object) -> tuple[Advisory, ...]:
    if not isinstance(items, list):
        return ()
    advisories: list[Advisory] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        package = item.get("package")
        fixed_in = item.get("fixed_in")
        if package and fixed_in:
            advisories.append(
                Advisory(
                    str(package).lower(),
                    str(fixed_in),
                    str(item.get("severity", "média")),
                    str(item.get("cve", "")),
                    str(item.get("title", "")),
                )
            )
    return tuple(advisories)
