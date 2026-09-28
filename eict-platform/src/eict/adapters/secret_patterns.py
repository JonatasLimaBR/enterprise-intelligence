"""Carrega o catálogo de padrões de segredo.

Fail-safe que **continua varrendo**: catálogo inválido/ausente ⇒ usa o `DEFAULT_POLICY` embutido.
Desligar a detecção de segredo em silêncio seria o pior desfecho — diferente das outras configs, aqui
a falha-segura é seguir com os padrões embutidos, não parar.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from eict.domain.secret_scan import SecretPattern, SecretScanPolicy

logger = logging.getLogger(__name__)

FILENAME = "patterns.yaml"

DEFAULT_PATTERNS = (
    SecretPattern("aws_access_key", r"AKIA[0-9A-Z]{16}", "alta"),
    SecretPattern("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "alta"),
    SecretPattern("databricks_token", r"dapi[0-9a-f]{32}", "alta"),
    SecretPattern(
        "generic_secret",
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        "média",
    ),
)
DEFAULT_POLICY = SecretScanPolicy(patterns=DEFAULT_PATTERNS)


def load_policy(directory: str | Path) -> SecretScanPolicy:
    if not directory:
        return DEFAULT_POLICY
    path = Path(directory)
    if path.is_dir():
        path = path / FILENAME
    if not path.exists():
        logger.info("catálogo de segredos não encontrado: %s; usando embutido", path)
        return DEFAULT_POLICY
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("catálogo de segredos %s recusado: %s; usando embutido", path, exc)
        return DEFAULT_POLICY
    if not isinstance(raw, dict):
        logger.warning("catálogo de segredos %s não é um mapa; usando embutido", path)
        return DEFAULT_POLICY
    patterns = _parse_patterns(raw.get("patterns"))
    if not patterns:
        logger.warning("catálogo de segredos %s sem padrões válidos; usando embutido", path)
        return DEFAULT_POLICY
    entropy = raw.get("entropy") or {}
    return SecretScanPolicy(
        patterns=patterns,
        entropy_min_len=int(entropy.get("min_len", 20)),
        entropy_min_bits=float(entropy.get("min_bits", 4.0)),
        mask_prefix=int(raw.get("mask_prefix", 4)),
    )


def _parse_patterns(items: object) -> tuple[SecretPattern, ...]:
    if not isinstance(items, list):
        return ()
    patterns: list[SecretPattern] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        nome = item.get("name")
        regex = item.get("regex")
        severidade = item.get("severity", "média")
        if nome and regex:
            patterns.append(SecretPattern(str(nome), str(regex), str(severidade)))
    return tuple(patterns)
