"""Carrega e valida `notifications/whatsapp.yaml`.

Fail-safe: arquivo ausente, YAML inválido ou config sem os campos mínimos ⇒ devolve `None`, e o
job `notify` não envia nada. Nunca lê o token daqui — o token vem do secret scope.
"""

from __future__ import annotations

import logging
from datetime import time
from pathlib import Path

import yaml

from eict.domain.notifications import NotificationConfig

logger = logging.getLogger(__name__)

FILENAME = "whatsapp.yaml"


def _parse_time(value: object, fallback: time) -> time:
    if not value:
        return fallback
    hour, _, minute = str(value).partition(":")
    return time(int(hour), int(minute or 0))


def load_config(directory: str | Path) -> NotificationConfig | None:
    if not directory:
        return None
    path = Path(directory)
    if path.is_dir():
        path = path / FILENAME
    if not path.exists():
        logger.info("config de notificação não encontrada: %s", path)
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("config de notificação %s recusada: %s", path, exc)
        return None
    if not isinstance(raw, dict):
        logger.warning("config de notificação %s não é um mapa", path)
        return None
    quiet = raw.get("quiet_hours") or {}
    config = NotificationConfig(
        destination=str(raw.get("destination") or ""),
        opt_in=bool(raw.get("opt_in", False)),
        threshold=str(raw.get("threshold") or "high"),
        template_name=str(raw.get("template_name") or ""),
        phone_number_id=str(raw.get("phone_number_id") or ""),
        template_lang=str(raw.get("template_lang") or "pt_BR"),
        console_url=str(raw.get("console_url") or ""),
        quiet_start=_parse_time(quiet.get("start"), time(22, 0)),
        quiet_end=_parse_time(quiet.get("end"), time(7, 0)),
        quiet_tz=str(quiet.get("tz") or "America/Sao_Paulo"),
        lookback_hours=int(raw.get("lookback_hours") or 24),
    )
    if not config.usable:
        logger.info("config de notificação incompleta ou opt-out; nada será enviado")
    return config
