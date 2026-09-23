from __future__ import annotations

from datetime import timedelta

from eict.domain.models import Change
from eict.domain.quality_hypotheses import (
    MAX_INFERRED_CONFIDENCE,
    TEMPORAL_ONLY_CAP,
    QualityContext,
    analyze,
)
from tests.conftest import BASE_TIME

NOW = BASE_TIME + timedelta(hours=8)
INCIDENT = "inc-qualidade"
ASSET = "workspace.eict_workload.sales_daily"
PRODUCER = "sales_daily"


def make_context(**kwargs) -> QualityContext:
    base = {
        "asset": ASSET,
        "dimension": "completeness",
        "rule_expression": "customer_id",
        "producer_job_id": PRODUCER,
    }
    return QualityContext(**{**base, **kwargs})


def commit_no_produtor(patch: str = "+ .withColumn('customer_id', F.lit(None))") -> Change:
    return Change(
        sha="d" * 40,
        repo="acme/eict",
        author="dev@example.com",
        committed_at=BASE_TIME + timedelta(hours=7),
        message="refactor: ajusta enriquecimento",
        files=("eict-demo-workload/src/sales_daily.py",),
        patch=patch,
    )


def commit_alheio() -> Change:
    return Change(
        sha="e" * 40,
        repo="acme/eict",
        author="dev@example.com",
        committed_at=BASE_TIME + timedelta(hours=7),
        message="docs: atualiza readme",
        files=("README.md",),
        patch="+ documentação",
    )


def top(analysis):
    return analysis.hypotheses[0]


def test_at013_produtor_parado_lidera_em_violacao_de_freshness():
    context = make_context(
        dimension="freshness", producer_ran_in_window=False, rule_expression=""
    )

    analysis = analyze(context, INCIDENT, NOW)

    assert top(analysis).code == "pipeline_failure"
    assert top(analysis).confidence >= 0.7


def test_produtor_que_rodou_bem_vira_evidencia_contra():
    analysis = analyze(make_context(), INCIDENT, NOW)

    pipeline = next(h for h in analysis.hypotheses if h.code == "pipeline_failure")

    assert pipeline.contradicting
    assert pipeline.confidence == 0.05


def test_at014_commit_no_produtor_que_toca_a_coluna_lidera():
    context = make_context(changes=(commit_no_produtor(),))

    analysis = analyze(context, INCIDENT, NOW)

    assert top(analysis).code == "code_change"
    assert top(analysis).confidence >= 0.6
    assert len(top(analysis).supporting) == 2


def test_commit_no_produtor_sem_tocar_a_coluna_pontua_menos():
    context = make_context(changes=(commit_no_produtor(patch="+ comentário inofensivo"),))

    analysis = analyze(context, INCIDENT, NOW)
    code_change = next(h for h in analysis.hypotheses if h.code == "code_change")

    assert code_change.confidence == 0.30


def test_sem_commit_a_hipotese_de_codigo_registra_evidencia_ausente():
    analysis = analyze(make_context(), INCIDENT, NOW)

    code_change = next(h for h in analysis.hypotheses if h.code == "code_change")

    assert code_change.confidence == 0.0
    assert code_change.missing


def test_mudanca_de_schema_na_origem_explica_violacao_estrutural():
    context = make_context(dimension="referential", upstream_schema_changed=True)

    analysis = analyze(context, INCIDENT, NOW)

    assert top(analysis).code == "upstream_change"
    assert top(analysis).confidence >= 0.55


def test_origem_intacta_derruba_a_hipotese_de_upstream():
    analysis = analyze(make_context(), INCIDENT, NOW)

    upstream = next(h for h in analysis.hypotheses if h.code == "upstream_change")

    assert upstream.contradicting
    assert not upstream.supporting


def test_violacao_tambem_na_origem_indica_qualidade_da_fonte():
    context = make_context(source_also_violates=True)

    analysis = analyze(context, INCIDENT, NOW)

    assert top(analysis).code == "data_source_quality"
    assert top(analysis).confidence >= 0.55


def test_origem_limpa_vira_evidencia_contra_qualidade_da_fonte():
    analysis = analyze(make_context(), INCIDENT, NOW)

    fonte = next(h for h in analysis.hypotheses if h.code == "data_source_quality")

    assert fonte.contradicting
    assert "transformação" in fonte.contradicting[0] or fonte.confidence == 0.05


def test_at015_commit_alheio_fica_limitado_a_correlacao_temporal():
    context = make_context(changes=(commit_alheio(),))

    analysis = analyze(context, INCIDENT, NOW)
    temporal = next(h for h in analysis.hypotheses if h.code == "change_temporal_only")

    assert temporal.confidence <= TEMPORAL_ONLY_CAP
    assert temporal.missing


def test_nenhuma_hipotese_ultrapassa_o_teto():
    context = make_context(
        dimension="freshness",
        producer_failed=True,
        upstream_schema_changed=True,
        source_also_violates=True,
        changes=(commit_no_produtor(),),
    )

    analysis = analyze(context, INCIDENT, NOW)

    assert all(h.confidence <= MAX_INFERRED_CONFIDENCE for h in analysis.hypotheses)
    assert all(h.status == "proposed" for h in analysis.hypotheses)


def test_hipoteses_sao_identificadas_pelo_incidente():
    primeira = analyze(make_context(), INCIDENT, NOW)
    segunda = analyze(make_context(dimension="uniqueness"), INCIDENT, NOW)

    assert {h.hypothesis_id for h in primeira.hypotheses} <= {
        h.hypothesis_id for h in segunda.hypotheses
    }


def test_toda_hipotese_tem_evidencia_registrada():
    context = make_context(changes=(commit_no_produtor(),))

    analysis = analyze(context, INCIDENT, NOW)
    ids = {evidence.evidence_id for evidence in analysis.evidence}

    for hypothesis in analysis.hypotheses:
        citados = set(hypothesis.supporting + hypothesis.contradicting + hypothesis.missing)
        assert citados <= ids


def test_produtor_parado_nao_explica_violacao_de_schema():
    """Um pipeline que não rodou deixa o dado velho, não com coluna a menos."""
    contexto = make_context(dimension="schema", producer_ran_in_window=False)

    analise = analyze(contexto, INCIDENT, NOW)
    pipeline = next(h for h in analise.hypotheses if h.code == "pipeline_failure")

    assert pipeline.confidence == 0.05
    assert pipeline.contradicting
    assert pipeline.rank > 1


def test_produtor_parado_continua_explicando_freshness():
    contexto = make_context(dimension="freshness", producer_ran_in_window=False)

    analise = analyze(contexto, INCIDENT, NOW)
    pipeline = next(h for h in analise.hypotheses if h.code == "pipeline_failure")

    assert pipeline.confidence == 0.75
    assert pipeline.rank == 1


def test_violacao_referencial_com_produtor_parado_tambem_e_contradita():
    contexto = make_context(dimension="referential", producer_failed=True)

    analise = analyze(contexto, INCIDENT, NOW)
    pipeline = next(h for h in analise.hypotheses if h.code == "pipeline_failure")

    assert pipeline.confidence == 0.05
