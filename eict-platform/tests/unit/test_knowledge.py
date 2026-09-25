"""Semelhantes, eficácia de runbook e conhecimento (AT-06…14, AT-16)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eict.domain.knowledge import (
    FALHA,
    PENDENTE,
    SUCESSO,
    efficacy,
    knowledge_item,
    outcome,
    similar,
)

AGORA = datetime(2026, 9, 25, 12, tzinfo=UTC)
SALES = "workspace.eict_workload.sales_daily"
ORDERS = "workspace.eict_workload.orders"


def _inc(i, subject=SALES, tipo="contract_violation", state="recovered", dias=5, horas=3):
    detectado = AGORA - timedelta(days=dias)
    return {
        "incident_id": f"inc-{i}",
        "subject": subject,
        "type": tipo,
        "state": state,
        "detected_at": detectado,
        "updated_at": detectado + timedelta(hours=horas),
    }


ATUAL = _inc(0, state="detected", dias=0)


def test_at06_nivel_1_mesmo_problema_neste_ativo():
    outro = _inc(1)
    [item] = similar(ATUAL, [ATUAL, outro], {"inc-0": "pipeline_failure", "inc-1": "pipeline_failure"}, AGORA)

    assert (item.level, item.reason) == (1, "mesmo problema neste ativo")
    assert item.hours_to_recover == 3.0


def test_at07_nivel_2_mesma_causa_em_outro_ativo():
    outro = _inc(1, subject=ORDERS)
    [item] = similar(ATUAL, [outro], {"inc-0": "pipeline_failure", "inc-1": "pipeline_failure"}, AGORA)

    assert (item.level, item.reason) == (2, "mesma causa em orders")


def test_nivel_3_mesmo_sintoma_neste_ativo():
    outro = _inc(1)
    [item] = similar(ATUAL, [outro], {"inc-0": "pipeline_failure", "inc-1": "upstream_change"}, AGORA)

    assert (item.level, item.reason) == (3, "mesmo sintoma neste ativo")


def test_tipo_diferente_nao_e_semelhante():
    outro = _inc(1, tipo="runtime_regression")

    assert similar(ATUAL, [outro], {}, AGORA) == []


def test_ordem_nivel_depois_recuperado_depois_recente():
    causas = {"inc-0": "c", "inc-1": "c", "inc-2": "c", "inc-3": "x"}
    ativo_recente = _inc(1, state="detected", dias=1)
    recuperado_antigo = _inc(2, dias=20)
    nivel3 = _inc(3, dias=1)

    itens = similar(ATUAL, [nivel3, ativo_recente, recuperado_antigo], causas, AGORA)

    assert [item.similar_id for item in itens] == ["inc-2", "inc-1", "inc-3"]
    assert [item.rank for item in itens] == [1, 2, 3]


def test_at08_no_maximo_5():
    outros = [_inc(i, dias=i) for i in range(1, 9)]
    causas = {item["incident_id"]: "c" for item in [ATUAL, *outros]}

    assert len(similar(ATUAL, outros, causas, AGORA)) == 5


def test_at09_mais_de_90_dias_fica_de_fora():
    assert similar(ATUAL, [_inc(1, dias=100)], {"inc-0": "c", "inc-1": "c"}, AGORA) == []


def test_o_proprio_incidente_nunca_e_semelhante():
    assert similar(ATUAL, [ATUAL], {"inc-0": "c"}, AGORA) == []


# --- eficácia -----------------------------------------------------------------------------------

USO = AGORA - timedelta(days=2)


def _recuperado_depois(horas):
    return {"state": "recovered", "updated_at": USO + timedelta(hours=horas)}


def test_at10_recuperou_em_20h_e_sucesso():
    assert outcome(USO, _recuperado_depois(20), AGORA) == (SUCESSO, 20.0)


def test_at11_recuperou_em_30h_nao_conta():
    assert outcome(USO, _recuperado_depois(30), AGORA) == (FALHA, None)


def test_at12_aberto_ha_menos_de_24h_e_pendente():
    uso_recente = AGORA - timedelta(hours=5)

    assert outcome(uso_recente, {"state": "detected"}, AGORA) == (PENDENTE, None)


def test_aberto_ha_mais_de_24h_e_falha():
    assert outcome(USO, {"state": "triaged"}, AGORA) == (FALHA, None)


def test_at13_fechado_por_decisao_nao_e_recuperar():
    assert outcome(USO, {"state": "closed", "updated_at": USO + timedelta(hours=1)}, AGORA) == (FALHA, None)


def test_eficacia_agrega_e_conta_uso_repetido_uma_vez():
    usos = [
        {"runbook_id": "RB-001", "incident_id": "a", "at": USO},
        {"runbook_id": "RB-001", "incident_id": "a", "at": USO + timedelta(hours=1)},  # repetido
        {"runbook_id": "RB-001", "incident_id": "b", "at": USO},
        {"runbook_id": "RB-001", "incident_id": "c", "at": AGORA - timedelta(hours=2)},
    ]
    incidentes = {
        "a": _recuperado_depois(10),
        "b": {"state": "closed", "updated_at": USO},
        "c": {"state": "detected"},
    }

    [item] = efficacy(usos, incidentes, AGORA)

    assert (item.uses, item.successes, item.failures, item.pending) == (3, 1, 1, 1)
    assert item.efficacy == 0.5
    assert item.median_hours_to_recover == 10.0
    assert item.small_sample


def test_sem_decisao_a_eficacia_e_nao_medida():
    usos = [{"runbook_id": "RB-001", "incident_id": "c", "at": AGORA - timedelta(hours=1)}]

    [item] = efficacy(usos, {"c": {"state": "detected"}}, AGORA)

    assert item.efficacy is None


# --- conhecimento -------------------------------------------------------------------------------

CANDIDATO = {
    "problem_id": "prb-1",
    "signature": f"contract_violation|{SALES}|pipeline_failure",
    "status": "resolvido",
}
REGISTRO = {
    "fix_description": "agendar o produtor antes do prazo",
    "known_error": "produtor manual",
    "workaround": "rodar à mão",
}


def test_at14_problema_resolvido_vira_conhecimento_ligado_ao_runbook():
    item = knowledge_item(CANDIDATO, REGISTRO, "RB-002")

    assert item.runbook_id == "RB-002"
    assert item.cause == "pipeline_failure"
    assert item.fix_description == "agendar o produtor antes do prazo"


def test_at16_sugestao_e_texto_com_a_correcao():
    item = knowledge_item(CANDIDATO, REGISTRO, "RB-002")

    assert item.suggestion.startswith("Acrescentar a RB-002")
    assert "agendar o produtor antes do prazo" in item.suggestion
    assert "Known error: produtor manual" in item.suggestion


def test_problema_nao_resolvido_nao_vira_conhecimento():
    assert knowledge_item({**CANDIDATO, "status": "em_observacao"}, REGISTRO, "RB-002") is None


def test_sem_runbook_sugere_criar_um():
    item = knowledge_item(CANDIDATO, REGISTRO, "")

    assert "um runbook novo para este tipo" in item.suggestion
