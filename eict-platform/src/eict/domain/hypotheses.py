from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from eict.domain.diff import new_plan_operators
from eict.domain.models import Change, Evidence, Hypothesis, RunFeatures, stable_id

POLICY_VERSION = "hyp-rules-v1"
MAX_INFERRED_CONFIDENCE = 0.9
TEMPORAL_ONLY_CAP = 0.5
SKEW_RATIO_THRESHOLD = 10.0
VOLUME_GROWTH_THRESHOLD = 1.5

SKEW_OPERATOR_RE = re.compile(r"Window|Exchange hashpartitioning")
SKEW_PATCH_RE = re.compile(r"\bjoin\b|Window|partitionBy", re.IGNORECASE)

WEIGHT_SKEW_RATIO = 0.35
WEIGHT_NEW_OPERATOR = 0.25
WEIGHT_PATCH_MATCH = 0.25
WEIGHT_VOLUME_STABLE = 0.05
WEIGHT_VOLUME_GROWTH = 0.40
WEIGHT_ENV_CHANGE = 0.50
CONTRADICTED_CONFIDENCE = 0.05
TEMPORAL_ONLY_CONFIDENCE = 0.30


@dataclass(frozen=True)
class Analysis:
    hypotheses: tuple[Hypothesis, ...]
    evidence: tuple[Evidence, ...]


def analyze(
    current: RunFeatures,
    healthy: RunFeatures | None,
    changes: list[Change],
    now: datetime,
    scope_id: str | None = None,
) -> Analysis:
    collected: dict[str, Evidence] = {}

    def record(kind: str, source_ref: str, summary: str, value: object | None = None) -> str:
        evidence = Evidence.create(kind, source_ref, now, summary, value)
        collected[evidence.evidence_id] = evidence
        return evidence.evidence_id

    scope = scope_id or current.run_id
    hypotheses = [
        _skew_hypothesis(current, healthy, changes, record, scope),
        _volume_hypothesis(current, healthy, record, scope),
        _compute_hypothesis(current, healthy, record, scope),
    ]
    temporal = _temporal_hypothesis(current, changes, record, scope)
    if temporal is not None:
        hypotheses.append(temporal)
    return Analysis(tuple(rank(hypotheses)), tuple(collected.values()))


def rank(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    capped = [
        hypothesis.with_confidence(
            min(
                hypothesis.confidence,
                TEMPORAL_ONLY_CAP
                if hypothesis.code == "change_temporal_only"
                else MAX_INFERRED_CONFIDENCE,
            )
        )
        for hypothesis in hypotheses
    ]
    ordered = sorted(capped, key=lambda hypothesis: (-hypothesis.confidence, hypothesis.code))
    return [hypothesis.with_rank(index + 1) for index, hypothesis in enumerate(ordered)]


def _skew_hypothesis(current, healthy, changes, record, scope: str) -> Hypothesis:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    confidence = 0.0

    profile = current.profile
    if profile is not None and profile.skew_ratio >= SKEW_RATIO_THRESHOLD:
        confidence += WEIGHT_SKEW_RATIO
        supporting.append(
            record(
                "data_skew",
                f"run_profile/{current.run_id}",
                f"chave {profile.key}={profile.hot_key} concentra {profile.top_key_share:.1%} "
                f"das linhas; skew_ratio={profile.skew_ratio:.1f}x",
                profile.skew_ratio,
            )
        )
    elif profile is None:
        missing.append(
            record("run_profile", f"run/{current.run_id}", "run profile ausente para o run atual")
        )

    operators = new_plan_operators(healthy, current)
    skew_operators = tuple(op for op in operators if SKEW_OPERATOR_RE.search(op))
    if skew_operators:
        confidence += WEIGHT_NEW_OPERATOR
        supporting.append(
            record(
                "plan_operator",
                f"run_profile/{current.run_id}",
                f"operadores novos no plano: {', '.join(skew_operators)}",
                list(skew_operators),
            )
        )

    suspect_change = _first_matching_change(changes)
    if suspect_change is not None:
        confidence += WEIGHT_PATCH_MATCH
        supporting.append(
            record(
                "change",
                f"commit/{suspect_change.sha}",
                f"commit {suspect_change.sha[:8]} altera {', '.join(suspect_change.files[:3])} "
                "com join/Window/partitionBy",
                suspect_change.sha,
            )
        )

    growth = _volume_growth(current, healthy)
    if growth is not None and growth < VOLUME_GROWTH_THRESHOLD:
        confidence += WEIGHT_VOLUME_STABLE
        supporting.append(
            record(
                "volume",
                f"run/{current.run_id}",
                f"volume de entrada estável ({growth:.2f}x do run saudável)",
                growth,
            )
        )

    missing.append(
        record(
            "spill_gc",
            f"run/{current.run_id}",
            "spill e GC não disponíveis: workspace serverless não expõe métricas por task",
        )
    )

    statement = (
        "Skew na chave do join/window introduzido por mudança de código "
        "degradou o tempo de execução"
    )
    return Hypothesis(
        hypothesis_id=stable_id("hyp", scope, "skew_join_change"),
        code="skew_join_change",
        statement=statement,
        confidence=confidence,
        supporting=tuple(supporting),
        contradicting=tuple(contradicting),
        missing=tuple(missing),
        policy_version=POLICY_VERSION,
    )


def _volume_hypothesis(current, healthy, record, scope: str) -> Hypothesis:
    growth = _volume_growth(current, healthy)
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []

    if growth is None:
        confidence = 0.0
        missing.append(
            record("volume", f"run/{current.run_id}", "contagem de linhas de entrada indisponível")
        )
    elif growth >= VOLUME_GROWTH_THRESHOLD:
        confidence = WEIGHT_VOLUME_GROWTH
        supporting.append(
            record(
                "volume",
                f"run/{current.run_id}",
                f"volume de entrada cresceu {growth:.2f}x em relação ao run saudável",
                growth,
            )
        )
    else:
        confidence = CONTRADICTED_CONFIDENCE
        contradicting.append(
            record(
                "volume",
                f"run/{current.run_id}",
                f"volume de entrada praticamente igual ({growth:.2f}x)",
                growth,
            )
        )

    return Hypothesis(
        hypothesis_id=stable_id("hyp", scope, "volume_growth"),
        code="volume_growth",
        statement="Crescimento do volume de entrada explica o tempo maior",
        confidence=confidence,
        supporting=tuple(supporting),
        contradicting=tuple(contradicting),
        missing=tuple(missing),
        policy_version=POLICY_VERSION,
    )


def _compute_hypothesis(current, healthy, record, scope: str) -> Hypothesis:
    supporting: list[str] = []
    contradicting: list[str] = []
    missing: list[str] = []
    current_env = current.run.env_hash
    healthy_env = healthy.run.env_hash if healthy is not None else None

    if current_env is None or healthy_env is None:
        confidence = 0.0
        missing.append(
            record("environment", f"run/{current.run_id}", "hash do ambiente indisponível")
        )
    elif current_env != healthy_env:
        confidence = WEIGHT_ENV_CHANGE
        supporting.append(
            record(
                "environment",
                f"run/{current.run_id}",
                f"ambiente mudou: {healthy_env} → {current_env}",
                current_env,
            )
        )
    else:
        confidence = CONTRADICTED_CONFIDENCE
        contradicting.append(
            record(
                "environment",
                f"run/{current.run_id}",
                f"ambiente idêntico ao run saudável ({current_env})",
                current_env,
            )
        )

    return Hypothesis(
        hypothesis_id=stable_id("hyp", scope, "compute_change"),
        code="compute_change",
        statement="Mudança de compute/ambiente explica o tempo maior",
        confidence=confidence,
        supporting=tuple(supporting),
        contradicting=tuple(contradicting),
        missing=tuple(missing),
        policy_version=POLICY_VERSION,
    )


def _temporal_hypothesis(current, changes, record, scope: str) -> Hypothesis | None:
    unrelated = [change for change in changes if not SKEW_PATCH_RE.search(change.patch)]
    if not unrelated:
        return None
    change = unrelated[0]
    evidence_id = record(
        "change",
        f"commit/{change.sha}",
        f"commit {change.sha[:8]} ocorreu na janela causal sem sinal técnico associado",
        change.sha,
    )
    return Hypothesis(
        hypothesis_id=stable_id("hyp", scope, "change_temporal_only"),
        code="change_temporal_only",
        statement="Alguma mudança recente não identificada explica o tempo maior",
        confidence=TEMPORAL_ONLY_CONFIDENCE,
        supporting=(evidence_id,),
        missing=(
            record(
                "causal_link",
                f"run/{current.run_id}",
                "correlação temporal isolada não estabelece causalidade",
            ),
        ),
        policy_version=POLICY_VERSION,
    )


def _first_matching_change(changes: list[Change]) -> Change | None:
    for change in changes:
        if SKEW_PATCH_RE.search(change.patch):
            return change
    return None


def _volume_growth(current: RunFeatures, healthy: RunFeatures | None) -> float | None:
    if healthy is None:
        return None
    current_rows = current.run.input_rows
    healthy_rows = healthy.run.input_rows
    if not current_rows or not healthy_rows:
        return None
    return current_rows / healthy_rows
