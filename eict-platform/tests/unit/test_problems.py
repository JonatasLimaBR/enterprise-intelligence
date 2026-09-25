"""Gestão de problemas (AT-01…12)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eict.domain.problems import (
    ABERTO,
    CANDIDATO,
    EM_OBSERVACAO,
    INEFICAZ,
    NO_HYPOTHESIS,
    RESOLVIDO,
    build,
    problem_id,
    signature,
    top_cause,
)

AGORA = datetime(2026, 9, 25, 12, tzinfo=UTC)
SALES = "workspace.eict_workload.sales_daily"


def _inc(i, dias_atras, tipo="contract_violation", subject=SALES, state="recovered", impact=0.85, horas=2):
    detectado = AGORA - timedelta(days=dias_atras)
    return {
        "incident_id": f"inc-{i}",
        "type": tipo,
        "subject": subject,
        "state": state,
        "detected_at": detectado,
        "updated_at": detectado + timedelta(hours=horas),
        "impact_score": impact,
    }


def _hip(code, rank=1, status="proposed"):
    return {"code": code, "rank": rank, "status": status}


def _hips(incidentes, code="pipeline_failure"):
    return {item["incident_id"]: [_hip(code)] for item in incidentes}


def test_at01_tres_na_janela_viram_candidato():
    incidentes = [_inc(i, dias) for i, dias in enumerate([2, 9, 20])]

    [candidato] = build(incidentes, _hips(incidentes), {}, AGORA)

    assert candidato.status == CANDIDATO
    assert candidato.incident_count == 3
    assert candidato.cause == "pipeline_failure"


def test_at02_dois_nao_bastam():
    incidentes = [_inc(i, dias) for i, dias in enumerate([2, 9])]

    assert build(incidentes, _hips(incidentes), {}, AGORA) == []


def test_at03_mesmo_ativo_causas_diferentes_sao_problemas_distintos():
    falha = [_inc(i, i + 1) for i in range(3)]
    upstream = [_inc(i + 10, i + 1) for i in range(3)]
    hips = {**_hips(falha), **_hips(upstream, "upstream_change")}

    candidatos = build(falha + upstream, hips, {}, AGORA)

    assert {item.cause for item in candidatos} == {"pipeline_failure", "upstream_change"}


def test_at04_fora_da_janela_nao_conta():
    incidentes = [_inc(0, 2), _inc(1, 9), _inc(2, 45)]

    assert build(incidentes, _hips(incidentes), {}, AGORA) == []


def test_at05_impacto_acumulado():
    incidentes = [_inc(i, i + 1, impact=0.5, horas=3) for i in range(3)]

    [candidato] = build(incidentes, _hips(incidentes), {}, AGORA)

    assert candidato.impact_score_sum == 1.5
    assert candidato.open_hours == 9.0


def test_incidente_ativo_conta_as_horas_ate_agora():
    incidentes = [_inc(0, 1, state="detected"), _inc(1, 2), _inc(2, 3)]

    [candidato] = build(incidentes, _hips(incidentes), {}, AGORA)

    assert candidato.open_hours == 24 + 2 + 2


def _promovido(incidentes, fix_dias_atras=None):
    pid = problem_id(signature(incidentes[0], "pipeline_failure"))
    fix = AGORA - timedelta(days=fix_dias_atras) if fix_dias_atras is not None else None
    return {pid: {"problem_id": pid, "fix_at": fix}}


def test_promovido_sem_correcao_esta_aberto():
    incidentes = [_inc(i, i + 5) for i in range(3)]

    [problema] = build(incidentes, _hips(incidentes), _promovido(incidentes), AGORA)

    assert problema.status == ABERTO


def test_at06_correcao_recente_em_observacao():
    incidentes = [_inc(i, i + 15) for i in range(3)]

    [problema] = build(incidentes, _hips(incidentes), _promovido(incidentes, fix_dias_atras=10), AGORA)

    assert problema.status == EM_OBSERVACAO
    assert "faltam 20 dia(s)" in problema.efficacy_detail


def test_at07_trinta_dias_sem_reincidencia_resolve():
    incidentes = [_inc(i, i + 40) for i in range(3)]

    [problema] = build(incidentes, _hips(incidentes), _promovido(incidentes, fix_dias_atras=31), AGORA)

    assert problema.status == RESOLVIDO


def test_at08_reincidencia_depois_da_correcao_e_ineficaz():
    incidentes = [_inc(i, i + 15) for i in range(3)] + [_inc(9, 2)]

    [problema] = build(incidentes, _hips(incidentes), _promovido(incidentes, fix_dias_atras=10), AGORA)

    assert problema.status == INEFICAZ
    assert "inc-9" in problema.efficacy_detail


def test_at09_hipotese_descartada_nao_define_a_causa():
    assert top_cause([_hip("skew_join_change", status="rejected"), _hip("code_change", rank=2)]) == "code_change"


def test_at10_sem_hipotese():
    assert top_cause([]) == NO_HYPOTHESIS
    assert signature({"type": "sla_risk", "subject": "x"}, NO_HYPOTHESIS) == "sla_risk|x|sem_hipotese"


def test_at11_id_estavel_por_assinatura():
    assert problem_id("a|b|c") == problem_id("a|b|c")
    assert problem_id("a|b|c") != problem_id("a|b|d")


def test_at12_promovido_abaixo_do_minimo_continua_acompanhado():
    incidentes = [_inc(0, 50)]

    [problema] = build(incidentes, _hips(incidentes), _promovido(incidentes, fix_dias_atras=40), AGORA)

    assert problema.status == RESOLVIDO
