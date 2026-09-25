"""Recomendações read-only: verificar e agir, com a base explícita."""

from __future__ import annotations

from eict.domain.recommendations import (
    ACT,
    CATALOG,
    COLLECT,
    MIN_CONFIDENCE,
    VERIFY,
    acceptance_rate,
    recommend,
)

INCIDENTE = {"incident_id": "inc-1", "type": "runtime_regression"}


def _hip(code, rank=1, confidence=0.9, status="proposed", missing=(), supporting=("ev-1", "ev-2")):
    return {
        "hypothesis_id": f"hyp-{code}",
        "code": code,
        "rank": rank,
        "confidence": confidence,
        "status": status,
        "missing": list(missing),
        "supporting": list(supporting),
    }


def test_hipotese_forte_gera_verificar_e_agir_citando_evidencias():
    recs = recommend(INCIDENTE, [_hip("skew_join_change")])

    assert [rec.kind for rec in recs] == [VERIFY, ACT]
    assert all(rec.evidence_ids == ("ev-1", "ev-2") for rec in recs)
    assert recs[0].basis == "inferida (confiança 0.90)"
    assert "salting" in recs[1].text


def test_hipotese_fraca_pede_a_evidencia_que_falta_em_vez_de_agir():
    recs = recommend(INCIDENTE, [_hip("code_change", confidence=0.3, missing=["diff do commit"])])

    assert [rec.kind for rec in recs] == [COLLECT]
    assert "diff do commit" in recs[0].text


def test_limite_de_confianca_e_inclusivo():
    assert recommend(INCIDENTE, [_hip("code_change", confidence=MIN_CONFIDENCE)])[0].kind == VERIFY


def test_hipotese_descartada_por_revisao_e_ignorada():
    recs = recommend(
        INCIDENTE,
        [_hip("skew_join_change", status="rejected"), _hip("volume_growth", rank=2, confidence=0.6)],
    )

    assert recs[0].hypothesis_id == "hyp-volume_growth"


def test_confirmada_por_revisao_vence_e_dispensa_o_limiar():
    recs = recommend(
        INCIDENTE,
        [_hip("skew_join_change", confidence=0.9), _hip("code_change", rank=2, confidence=0.2, status="confirmed")],
    )

    assert recs[0].hypothesis_id == "hyp-code_change"
    assert recs[0].basis == "confirmada por revisão"


def test_incidente_sem_hipotese_usa_o_tipo():
    recs = recommend({"incident_id": "inc-2", "type": "sla_risk"}, [])

    assert [rec.kind for rec in recs] == [VERIFY, ACT]
    assert recs[1].basis == "tipo do incidente"
    assert recs[1].owner_role == "operador"


def test_tipo_desconhecido_sem_hipotese_nao_inventa():
    assert recommend({"incident_id": "inc-3", "type": "outro"}, []) == []


def test_id_estavel_por_incidente_hipotese_e_tipo():
    um = recommend(INCIDENTE, [_hip("skew_join_change")])
    dois = recommend(INCIDENTE, [_hip("skew_join_change", confidence=0.95)])

    assert [rec.recommendation_id for rec in um] == [rec.recommendation_id for rec in dois]


def test_todo_codigo_de_hipotese_tem_playbook():
    codigos = {
        "skew_join_change", "code_change", "compute_change", "volume_growth",
        "pipeline_failure", "upstream_change", "data_source_quality", "change_temporal_only",
    }
    assert codigos <= set(CATALOG)


def test_taxa_de_aceitas_ignora_pendentes():
    taxa, aceitas, decididas = acceptance_rate(
        [{"decision": "accepted"}, {"decision": "rejected"}, {"decision": "accepted"}, {"decision": None}]
    )

    assert (aceitas, decididas) == (2, 3)
    assert round(taxa, 3) == 0.667


def test_taxa_sem_decisao_e_nao_medida():
    assert acceptance_rate([]) == (None, 0, 0)
