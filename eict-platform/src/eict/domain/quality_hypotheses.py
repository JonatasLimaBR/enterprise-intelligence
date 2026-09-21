from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from eict.domain.hypotheses import (
    MAX_INFERRED_CONFIDENCE,
    TEMPORAL_ONLY_CAP,
    Analysis,
    rank,
)
from eict.domain.models import Change, Evidence, Hypothesis, stable_id

POLICY_VERSION = "quality-rules-v1"

WEIGHT_PRODUCER_FAILED = 0.50
WEIGHT_FRESHNESS_DIMENSION = 0.25
WEIGHT_COMMIT_TOUCHES_PRODUCER = 0.30
WEIGHT_PATCH_TOUCHES_COLUMN = 0.30
WEIGHT_UPSTREAM_CHANGED = 0.35
WEIGHT_STRUCTURAL_DIMENSION = 0.25
WEIGHT_SOURCE_ALSO_FAILS = 0.45
WEIGHT_NO_CHANGE = 0.15
CONTRADICTED_CONFIDENCE = 0.05
TEMPORAL_ONLY_CONFIDENCE = 0.30

STRUCTURAL_DIMENSIONS = frozenset({"schema", "referential"})


@dataclass(frozen=True)
class QualityContext:
    """O que se sabe sobre a violação, além do resultado da própria regra."""

    asset: str
    dimension: str
    rule_expression: str
    producer_job_id: str
    producer_failed: bool = False
    producer_ran_in_window: bool = True
    upstream_schema_changed: bool = False
    upstream_volume_changed: bool = False
    source_also_violates: bool = False
    changes: tuple[Change, ...] = ()


def analyze(context: QualityContext, incident_id: str, now: datetime) -> Analysis:
    collected: dict[str, Evidence] = {}

    def record(kind: str, source_ref: str, summary: str, value: object | None = None) -> str:
        evidence = Evidence.create(kind, source_ref, now, summary, value)
        collected[evidence.evidence_id] = evidence
        return evidence.evidence_id

    hypotheses = [
        _pipeline_failure(context, incident_id, record),
        _code_change(context, incident_id, record),
        _upstream_change(context, incident_id, record),
        _data_source_quality(context, incident_id, record),
    ]
    temporal = _temporal_only(context, incident_id, record)
    if temporal is not None:
        hypotheses.append(temporal)
    return Analysis(tuple(rank(hypotheses)), tuple(collected.values()))


def _pipeline_failure(context: QualityContext, incident_id: str, record) -> Hypothesis:
    supporting: list[str] = []
    contradicting: list[str] = []
    confidence = 0.0

    if context.producer_failed or not context.producer_ran_in_window:
        confidence += WEIGHT_PRODUCER_FAILED
        motivo = "falhou" if context.producer_failed else "não executou na janela"
        supporting.append(
            record(
                "producer_state",
                f"job/{context.producer_job_id}",
                f"job produtor {context.producer_job_id} {motivo}",
                context.producer_job_id,
            )
        )
    else:
        contradicting.append(
            record(
                "producer_state",
                f"job/{context.producer_job_id}",
                f"job produtor {context.producer_job_id} executou com sucesso na janela",
            )
        )
        confidence = CONTRADICTED_CONFIDENCE

    if context.dimension == "freshness" and confidence > CONTRADICTED_CONFIDENCE:
        confidence += WEIGHT_FRESHNESS_DIMENSION
        supporting.append(
            record(
                "dimension",
                f"asset/{context.asset}",
                "violação é de freshness, compatível com produtor parado",
            )
        )

    return Hypothesis(
        hypothesis_id=stable_id("hyp", incident_id, "pipeline_failure"),
        code="pipeline_failure",
        statement="O pipeline produtor não rodou ou falhou, deixando o dado desatualizado",
        confidence=confidence,
        supporting=tuple(supporting),
        contradicting=tuple(contradicting),
        policy_version=POLICY_VERSION,
    )


def _code_change(context: QualityContext, incident_id: str, record) -> Hypothesis:
    supporting: list[str] = []
    missing: list[str] = []
    confidence = 0.0

    suspeito = _change_touching_producer(context)
    if suspeito is not None:
        confidence += WEIGHT_COMMIT_TOUCHES_PRODUCER
        supporting.append(
            record(
                "change",
                f"commit/{suspeito.sha}",
                f"commit {suspeito.sha[:8]} altera o job produtor "
                f"({', '.join(suspeito.files[:3])})",
                suspeito.sha,
            )
        )
        if _patch_mentions_column(suspeito, context.rule_expression):
            confidence += WEIGHT_PATCH_TOUCHES_COLUMN
            supporting.append(
                record(
                    "change_detail",
                    f"commit/{suspeito.sha}",
                    f"o patch toca a coluna avaliada pela regra ({context.rule_expression})",
                    context.rule_expression,
                )
            )
    else:
        missing.append(
            record(
                "change",
                f"asset/{context.asset}",
                "nenhum commit na janela altera o job produtor",
            )
        )

    return Hypothesis(
        hypothesis_id=stable_id("hyp", incident_id, "code_change"),
        code="code_change",
        statement="Uma mudança de código no produtor introduziu a violação",
        confidence=confidence,
        supporting=tuple(supporting),
        missing=tuple(missing),
        policy_version=POLICY_VERSION,
    )


def _upstream_change(context: QualityContext, incident_id: str, record) -> Hypothesis:
    supporting: list[str] = []
    contradicting: list[str] = []
    confidence = 0.0

    if context.upstream_schema_changed or context.upstream_volume_changed:
        confidence += WEIGHT_UPSTREAM_CHANGED
        o_que = "schema" if context.upstream_schema_changed else "volume"
        supporting.append(
            record(
                "upstream",
                f"asset/{context.asset}",
                f"{o_que} da origem mudou na janela",
                o_que,
            )
        )
        if context.dimension in STRUCTURAL_DIMENSIONS:
            confidence += WEIGHT_STRUCTURAL_DIMENSION
            supporting.append(
                record(
                    "dimension",
                    f"asset/{context.asset}",
                    f"violação de {context.dimension} é compatível com mudança na origem",
                )
            )
    else:
        confidence = CONTRADICTED_CONFIDENCE
        contradicting.append(
            record("upstream", f"asset/{context.asset}", "origem sem mudança de schema ou volume")
        )

    return Hypothesis(
        hypothesis_id=stable_id("hyp", incident_id, "upstream_change"),
        code="upstream_change",
        statement="Uma mudança na tabela de origem quebrou a expectativa do contrato",
        confidence=confidence,
        supporting=tuple(supporting),
        contradicting=tuple(contradicting),
        policy_version=POLICY_VERSION,
    )


def _data_source_quality(context: QualityContext, incident_id: str, record) -> Hypothesis:
    supporting: list[str] = []
    contradicting: list[str] = []
    confidence = 0.0

    if context.source_also_violates:
        confidence += WEIGHT_SOURCE_ALSO_FAILS
        supporting.append(
            record(
                "source_quality",
                f"asset/{context.asset}",
                "a mesma regra também falha na tabela de origem",
            )
        )
        if _change_touching_producer(context) is None and not context.upstream_schema_changed:
            confidence += WEIGHT_NO_CHANGE
            supporting.append(
                record(
                    "no_change",
                    f"asset/{context.asset}",
                    "nenhuma mudança de código ou schema na janela",
                )
            )
    else:
        confidence = CONTRADICTED_CONFIDENCE
        contradicting.append(
            record(
                "source_quality",
                f"asset/{context.asset}",
                "a origem passa na mesma regra: o problema nasce na transformação",
            )
        )

    return Hypothesis(
        hypothesis_id=stable_id("hyp", incident_id, "data_source_quality"),
        code="data_source_quality",
        statement="O dado já chega violado da origem",
        confidence=confidence,
        supporting=tuple(supporting),
        contradicting=tuple(contradicting),
        policy_version=POLICY_VERSION,
    )


def _temporal_only(context: QualityContext, incident_id: str, record) -> Hypothesis | None:
    nao_relacionados = [
        change for change in context.changes if not _touches_producer(change, context)
    ]
    if not nao_relacionados:
        return None
    change = nao_relacionados[0]
    return Hypothesis(
        hypothesis_id=stable_id("hyp", incident_id, "change_temporal_only"),
        code="change_temporal_only",
        statement="Alguma mudança recente não identificada explica a violação",
        confidence=TEMPORAL_ONLY_CONFIDENCE,
        supporting=(
            record(
                "change",
                f"commit/{change.sha}",
                f"commit {change.sha[:8]} na janela, sem relação com o produtor",
                change.sha,
            ),
        ),
        missing=(
            record(
                "causal_link",
                f"asset/{context.asset}",
                "correlação temporal isolada não estabelece causalidade",
            ),
        ),
        policy_version=POLICY_VERSION,
    )


def _change_touching_producer(context: QualityContext) -> Change | None:
    for change in context.changes:
        if _touches_producer(change, context):
            return change
    return None


def _touches_producer(change: Change, context: QualityContext) -> bool:
    alvo = context.producer_job_id.lower()
    return any(alvo in arquivo.lower() for arquivo in change.files)


def _patch_mentions_column(change: Change, expression: str) -> bool:
    colunas = re.findall(r"\b[a-z_][a-z0-9_]*\b", expression.lower())
    return any(coluna in change.patch.lower() for coluna in colunas if len(coluna) > 3)


__all__ = [
    "MAX_INFERRED_CONFIDENCE",
    "POLICY_VERSION",
    "TEMPORAL_ONLY_CAP",
    "QualityContext",
    "analyze",
]
