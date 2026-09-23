"""Divergência entre o declarado e o calculado vira incidente `semantic_conflict`.

Só as divergências bloqueantes abrem incidente — fórmula, grão, ou código contra a
definição canônica. Sinônimo e métrica sem declaração são achados de catálogo: aparecem
no console, mas não competem na fila com o que está quebrando número em painel.
"""

from __future__ import annotations

import json
from datetime import datetime

from eict.domain.extraction import ObservedMetric
from eict.domain.incidents import SEMANTIC_CONFLICT
from eict.domain.metrics import Divergence
from eict.domain.models import Evidence, stable_id

EVIDENCE_KIND = "semantic_divergence"
DEFAULT_SEVERITY = "warning"

Subject = tuple[str, str]


def group_conflicts(divergences: tuple[Divergence, ...] | list[Divergence]) -> dict[str, list[Divergence]]:
    """Agrupa por ativo: N métricas em conflito no mesmo ativo = 1 incidente."""
    grouped: dict[str, list[Divergence]] = {}
    for divergence in divergences:
        if divergence.is_blocking:
            grouped.setdefault(divergence.asset, []).append(divergence)
    return {
        asset: sorted(items, key=lambda item: (item.metric_id, item.kind))
        for asset, items in grouped.items()
    }


def evaluated_assets(
    observed: list[ObservedMetric], sources: tuple[tuple[str, str], ...]
) -> frozenset[str]:
    """Ativos cuja extração neste ciclo cobriu **todos** os arquivos do registry.

    Um ativo calculado em dois arquivos com fórmulas diferentes só tem conflito se os dois
    forem lidos. Se a busca de um deles falhar, o conflito some — e tratar o ativo como
    avaliado fecharia o incidente justamente porque faltou evidência.
    """
    esperados: dict[str, set[str]] = {}
    for path, asset in sources:
        esperados.setdefault(asset, set()).add(path)
    lidos: dict[str, set[str]] = {}
    for item in observed:
        if item.is_comparable:
            lidos.setdefault(item.asset, set()).add(item.source_path)
    return frozenset(
        asset for asset, paths in esperados.items() if paths <= lidos.get(asset, set())
    )


def current_state(
    observed: list[ObservedMetric],
    sources: tuple[tuple[str, str], ...],
    divergences: tuple[Divergence, ...] | list[Divergence],
) -> tuple[frozenset[Subject], frozenset[Subject]]:
    avaliados = evaluated_assets(observed, sources)
    violando = set(group_conflicts(divergences))
    return (
        frozenset((asset, SEMANTIC_CONFLICT) for asset in avaliados),
        frozenset((asset, SEMANTIC_CONFLICT) for asset in violando),
    )


def event_id(divergences: list[Divergence]) -> str:
    """Identidade do evento que abre o incidente: o conjunto de divergências, não o ciclo."""
    return stable_id(
        "div",
        *(f"{item.kind}|{item.metric_id}|{item.left}|{item.right}" for item in divergences),
    )


def build_evidence(
    divergence: Divergence, observed: list[ObservedMetric], now: datetime
) -> Evidence:
    """As duas definições, cada uma com arquivo e linha — sem precisar abrir o código."""
    fontes = sorted(
        (
            item
            for item in observed
            if item.asset == divergence.asset and item.metric_id == divergence.metric_id
        ),
        key=lambda item: (item.source_path, item.source_line),
    )
    payload = {
        "kind": divergence.kind,
        "metric_id": divergence.metric_id,
        "left": divergence.left,
        "right": divergence.right,
        "sources": [
            {
                "path": item.source_path,
                "line": item.source_line,
                "formula": item.formula_raw,
                "grain": list(item.grain),
                "status": item.status,
            }
            for item in fontes
        ],
    }
    return Evidence.create(
        kind=EVIDENCE_KIND,
        source_ref=f"metric/{divergence.asset}/{divergence.metric_id}/{divergence.kind}",
        observed_at=now,
        summary=divergence.detail,
        value=json.dumps(payload, ensure_ascii=False),
    )


def conflict_summary(asset: str, divergences: list[Divergence]) -> str:
    metricas = ", ".join(sorted({item.metric_id for item in divergences}))
    return f"{len(divergences)} divergência(s) semântica(s) em {asset}: {metricas}"
