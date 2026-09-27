"""Domínio da notificação: eventos materiais, limiar, dedup, quiet hours e variáveis (puro)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eict.domain.notifications import (
    NotificationConfig,
    NotificationError,
    in_quiet_hours,
    material_events,
    messages_for,
    render_variables,
    send_after,
)

# America/Sao_Paulo = UTC-3: 06:00 UTC = 03:00 local (dentro do quiet hours 22:00–07:00).
NOITE = datetime(2026, 9, 27, 6, 0, tzinfo=UTC)
DIA = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)  # 12:00 local

CFG = NotificationConfig(
    destination="+5511999999999",
    opt_in=True,
    threshold="high",
    template_name="eict_incident_alert",
    phone_number_id="123456",
    console_url="https://console.example",
)


def make_incident(**over):
    from eict.domain.models import Incident

    base = dict(
        incident_id="inc-1",
        correlation_key="k1",
        tenant_id="demo",
        subject="workspace.eict.orders",
        type="runtime_regression",
        state="triaged",
        severity="critical",
        first_run_id="r1",
        last_run_id="r2",
        detected_at=DIA,
        updated_at=DIA,
    )
    base.update(over)
    return Incident(**base)


def test_aberto_dispara_para_incidente_ativo_recente():
    eventos = material_events(make_incident(), CFG, DIA)
    assert ("aberto", "inc-1|aberto") in eventos


def test_aberto_nao_dispara_para_incidente_antigo():
    antigo = make_incident(detected_at=datetime(2026, 9, 1, tzinfo=UTC))
    assert material_events(antigo, CFG, DIA) == []


def test_escalou_dispara_e_carrega_a_nova_severidade():
    inc = make_incident(escalated_from="warning")
    eventos = dict(material_events(inc, CFG, DIA))
    assert eventos["escalou"] == "inc-1|escalou|critical"


def test_recuperado_dispara_mas_closed_nao():
    recuperado = make_incident(state="recovered")
    fechado = make_incident(state="closed")
    assert ("recuperado", "inc-1|recuperado") in material_events(recuperado, CFG, DIA)
    assert material_events(fechado, CFG, DIA) == []


def test_limiar_filtra_abaixo():
    baixo = make_incident(severity="warning")
    assert messages_for([baixo], CFG, DIA, {}) == []


def test_limiar_inclui_no_nivel():
    inc = make_incident(severity="high")
    mensagens = messages_for([inc], CFG, DIA, {})
    assert [m.event for m in mensagens] == ["aberto"]


def test_dedup_key_por_incidente_e_evento():
    inc = make_incident(escalated_from="high")
    mensagens = messages_for([inc], CFG, DIA, {})
    chaves = {m.dedup_key for m in mensagens}
    assert chaves == {"inc-1|aberto", "inc-1|escalou|critical"}


def test_critical_fura_quiet_hours():
    assert in_quiet_hours(NOITE, CFG) is True
    assert send_after(NOITE, "critical", CFG) == NOITE


def test_high_espera_o_fim_do_quiet_hours():
    quando = send_after(NOITE, "high", CFG)
    assert quando > NOITE
    # 07:00 local = 10:00 UTC
    assert quando == datetime(2026, 9, 27, 10, 0, tzinfo=UTC)


def test_fora_do_quiet_hours_envia_agora():
    assert in_quiet_hours(DIA, CFG) is False
    assert send_after(DIA, "high", CFG) == DIA


def test_variaveis_incluem_evidencias_e_link():
    inc = make_incident(affected_assets=("painel", "x"), impact_score=1.68)
    variaveis = render_variables(inc, "aberto", ("skew na chave", "operador novo", "extra"), CFG)
    assert variaveis[0] == "ABERTO · critical"
    assert variaveis[1] == "runtime_regression"
    assert variaveis[2] == "workspace.eict.orders"
    assert variaveis[3] == "1.68 (2 ativos)"
    assert variaveis[4] == "skew na chave · operador novo"  # top 2
    assert variaveis[5] == "https://console.example"


def test_variaveis_sem_evidencia_usam_texto_padrao():
    variaveis = render_variables(make_incident(), "aberto", (), CFG)
    assert variaveis[4] == "sem evidências resumidas"


def test_variavel_obrigatoria_vazia_recusa():
    inc = make_incident(subject="")
    with pytest.raises(NotificationError):
        render_variables(inc, "aberto", (), CFG)


def test_config_opt_out_nao_gera_mensagem():
    inc = make_incident()
    assert messages_for([inc], NotificationConfig(
        destination="+55", opt_in=False, threshold="high",
        template_name="t", phone_number_id="1",
    ), DIA, {}) == []
