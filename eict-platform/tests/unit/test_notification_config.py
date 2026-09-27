"""Carga da config de notificação: válida, inválida e opt-out (fail-safe)."""

from __future__ import annotations

from datetime import time

VALIDO = """
channel: whatsapp
phone_number_id: "123456"
destination: "+5511999999999"
opt_in: true
threshold: high
template_name: eict_incident_alert
console_url: "https://console.example"
quiet_hours:
  start: "23:00"
  end: "06:30"
  tz: America/Sao_Paulo
lookback_hours: 12
"""


def test_config_valida_e_usable(tmp_path):
    from eict.adapters.notification_config import load_config

    (tmp_path / "whatsapp.yaml").write_text(VALIDO, encoding="utf-8")
    cfg = load_config(tmp_path)

    assert cfg is not None and cfg.usable
    assert cfg.destination == "+5511999999999"
    assert cfg.quiet_start == time(23, 0)
    assert cfg.quiet_end == time(6, 30)
    assert cfg.lookback_hours == 12


def test_diretorio_sem_arquivo_devolve_none(tmp_path):
    from eict.adapters.notification_config import load_config

    assert load_config(tmp_path) is None


def test_caminho_vazio_devolve_none():
    from eict.adapters.notification_config import load_config

    assert load_config("") is None


def test_yaml_invalido_devolve_none(tmp_path):
    from eict.adapters.notification_config import load_config

    (tmp_path / "whatsapp.yaml").write_text("a: [1, 2\n", encoding="utf-8")
    assert load_config(tmp_path) is None


def test_opt_out_carrega_mas_nao_e_usable(tmp_path):
    from eict.adapters.notification_config import load_config

    (tmp_path / "whatsapp.yaml").write_text(VALIDO.replace("opt_in: true", "opt_in: false"), encoding="utf-8")
    cfg = load_config(tmp_path)

    assert cfg is not None and not cfg.usable


def test_sem_phone_number_id_nao_e_usable(tmp_path):
    from eict.adapters.notification_config import load_config

    sem_id = VALIDO.replace('phone_number_id: "123456"', 'phone_number_id: ""')
    (tmp_path / "whatsapp.yaml").write_text(sem_id, encoding="utf-8")
    cfg = load_config(tmp_path)

    assert cfg is not None and not cfg.usable
