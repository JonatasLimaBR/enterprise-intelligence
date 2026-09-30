"""Cliente do Jev (TypeSafe System One) e carga da config de advisors.

`decide` devolve `Answer` ou `None` (sem token, erro HTTP/rede, resposta ilegível) — nunca ergue para o
ciclo. Sem token/config, nada sai (egress desligado por padrão). Usa `requests` direto, sem SDK novo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

from eict.domain.jev_advisor import Answer, JevConfig

logger = logging.getLogger(__name__)

TIMEOUT_S = 15
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
FILENAME = "advisors.yaml"
KNOWN_ADVISORS = frozenset({"triage", "connector", "runbook"})


@dataclass(frozen=True)
class JevClient:
    token: str
    session: requests.Session | None = None

    def decide(self, state: dict, question: dict) -> Answer | None:
        if not self.token:
            return None
        payload = {"model": MODEL, "state": state, "questions": {"q": question}}
        try:
            response = (self.session or requests.Session()).post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                json=payload,
                timeout=TIMEOUT_S,
            )
        except requests.RequestException as exc:
            logger.info("jev indisponível: %s", exc)
            return None
        if response.status_code >= 400 or not response.content:
            logger.info("jev %s", response.status_code)
            return None
        answer = (response.json() or {}).get("q") or {}
        if "value" not in answer or "confidence" not in answer:
            return None
        return Answer(str(answer["value"]), float(answer["confidence"]))


def load_jev_config(directory: str | Path) -> JevConfig:
    """Ausente/inválida ⇒ nenhum advisor habilitado (egress desligado por padrão)."""
    if not directory:
        return JevConfig(frozenset())
    path = Path(directory)
    if path.is_dir():
        path = path / FILENAME
    if not path.exists():
        return JevConfig(frozenset())
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("config jev %s recusada: %s; tudo desligado", path, exc)
        return JevConfig(frozenset())
    if not isinstance(raw, dict):
        return JevConfig(frozenset())
    habilitados = frozenset(str(item) for item in (raw.get("enabled") or []) if str(item) in KNOWN_ADVISORS)
    try:
        limiar = float(raw.get("threshold", 0.70))
    except (TypeError, ValueError):
        limiar = 0.70
    return JevConfig(habilitados, limiar)
