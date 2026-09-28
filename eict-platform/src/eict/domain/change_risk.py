"""Score de risco por commit: combina blast radius, histórico, tamanho e proveniência.

Puro. Tamanho e proveniência são calculados aqui do próprio `Change`; blast e histórico chegam
prontos (o job os resolve com o impact engine e os incidentes). Determinístico: mesma entrada,
mesmo score — o que permite virar policy na feature 4.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubScore:
    value: float
    reason: str


@dataclass(frozen=True)
class BlastInput:
    score: float
    reaches_human: bool
    assets: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class HistoryInput:
    incidents: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ChangeRiskWeights:
    blast: float = 0.40
    history: float = 0.30
    size: float = 0.20
    provenance: float = 0.10
    band_low: float = 0.34
    band_high: float = 0.66
    files_cap: int = 10
    lines_cap: int = 400
    history_denom: int = 3
    history_days: int = 14
    asset_anchor: float = 3.0
    author_patterns: tuple[str, ...] = ("[bot]", "noreply", "actions")
    trailer_patterns: tuple[str, ...] = ("generated-by:", "co-authored-by:")


@dataclass(frozen=True)
class ChangeRisk:
    sha: str
    total: float
    band: str
    blast: SubScore
    history: SubScore
    size: SubScore
    provenance: SubScore
    assets: tuple[str, ...]
    contributors: tuple[str, ...] = ()


def size_subscore(files: tuple[str, ...], patch: str, weights: ChangeRiskWeights) -> SubScore:
    lines = sum(1 for line in patch.splitlines() if line[:1] in {"+", "-"})
    value = min(1.0, 0.5 * len(files) / weights.files_cap + 0.5 * lines / weights.lines_cap)
    return SubScore(round(value, 4), f"{len(files)} arquivo(s), {lines} linha(s) de patch")


def provenance_subscore(author: str, message: str, weights: ChangeRiskWeights) -> SubScore:
    author_lower = author.lower()
    message_lower = message.lower()
    by_author = any(pattern in author_lower for pattern in weights.author_patterns)
    by_trailer = any(pattern in message_lower for pattern in weights.trailer_patterns)
    if by_author or by_trailer:
        origem = "autor de automação" if by_author else "trailer de geração"
        return SubScore(1.0, f"automação/IA ({origem})")
    return SubScore(0.0, "autor humano conhecido")


def history_subscore(history: HistoryInput, weights: ChangeRiskWeights) -> SubScore:
    value = min(1.0, len(history.incidents) / weights.history_denom)
    return SubScore(round(value, 4), history.reason)


def band_of(total: float, weights: ChangeRiskWeights) -> str:
    if total > weights.band_high:
        return "alto"
    return "baixo" if total < weights.band_low else "médio"


def score_change(change, blast: BlastInput, history: HistoryInput, weights: ChangeRiskWeights) -> ChangeRisk:
    blast_s = SubScore(round(blast.score, 4), blast.reason)
    history_s = history_subscore(history, weights)
    size_s = size_subscore(change.files, change.patch, weights)
    provenance_s = provenance_subscore(change.author, change.message, weights)
    total = round(
        weights.blast * blast_s.value
        + weights.history * history_s.value
        + weights.size * size_s.value
        + weights.provenance * provenance_s.value,
        4,
    )
    return ChangeRisk(
        sha=change.sha,
        total=total,
        band=band_of(total, weights),
        blast=blast_s,
        history=history_s,
        size=size_s,
        provenance=provenance_s,
        assets=blast.assets,
    )
