"""Estágio `change_risk`: pontua os commits de `silver.changes` (read-only).

Roda depois do `correlate` — incidentes e `ops.lineage_graph` já estão frescos. Resolve, por commit,
os assets (registry), o blast radius (impact engine) e o histórico (incidentes nos mesmos assets), e
grava o read model `ops.change_risk`. Nada é bloqueado nem executado.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from eict.adapters import lineage, store
from eict.adapters.change_risk_config import load_weights
from eict.adapters.metric_loader import load_registry
from eict.config import Settings, parse_settings
from eict.domain import impact
from eict.domain.change_risk import (
    BlastInput,
    ChangeRisk,
    ChangeRiskWeights,
    HistoryInput,
    score_change,
)
from eict.jobs.correlate import load_changes

logger = logging.getLogger(__name__)

POLICY_VERSION = "change-risk-v1"
MAX_REASON_INCIDENTS = 3


def assets_for(files: tuple[str, ...], sources: tuple[tuple[str, str], ...]) -> tuple[str, ...]:
    achados: set[str] = set()
    for arquivo in files:
        base = os.path.basename(arquivo)
        for caminho, ativo in sources:
            if arquivo == caminho or arquivo.endswith(caminho) or base == os.path.basename(caminho):
                achados.add(ativo)
    return tuple(sorted(achados))


def blast_for(
    assets: tuple[str, ...], edges: tuple, now: datetime, weights: ChangeRiskWeights, settings: Settings
) -> BlastInput:
    if not assets:
        return BlastInput(0.0, False, (), "sem asset mapeado")
    soma_max, alcanca, nos = 0.0, False, 0
    for asset in assets:
        result = impact.traverse(
            edges, asset, now, max_depth=settings.impact_max_depth, excluded=settings.excluded_assets
        )
        soma_max = max(soma_max, result.score)
        alcanca = alcanca or any(node.is_human_consumption for node in result.nodes)
        nos += len(result.nodes)
    score = 1.0 if alcanca else min(1.0, soma_max / weights.asset_anchor)
    motivo = f"{nos} nó(s) no raio de {len(assets)} asset(s)" + (
        " — atinge consumo humano" if alcanca else ""
    )
    return BlastInput(round(score, 4), alcanca, assets, motivo)


def load_incident_assets(spark: Any, settings: Settings) -> list[dict]:
    return store.query(
        spark,
        f"SELECT incident_id, affected_assets, detected_at FROM {settings.table('ops', 'incidents')}",
    )


def history_for(
    assets: tuple[str, ...],
    incidents: list[dict],
    changes_at_by_asset: dict[str, list[datetime]],
    weights: ChangeRiskWeights,
) -> HistoryInput:
    if not assets:
        return HistoryInput((), "sem asset mapeado")
    conjunto = set(assets)
    janela = timedelta(days=weights.history_days)
    casados: list[str] = []
    for incidente in incidents:
        atingidos = conjunto.intersection(incidente.get("affected_assets") or ())
        if not atingidos:
            continue
        detectado = incidente.get("detected_at")
        if detectado is None:
            continue
        mudou_antes = any(
            0 <= (detectado - committed).total_seconds() <= janela.total_seconds()
            for ativo in atingidos
            for committed in changes_at_by_asset.get(ativo, ())
        )
        if mudou_antes:
            casados.append(incidente["incident_id"])
    if not casados:
        return HistoryInput((), "sem incidentes nos assets após mudança recente")
    amostra = ", ".join(casados[:MAX_REASON_INCIDENTS])
    return HistoryInput(tuple(casados), f"{len(casados)} incidente(s) nos assets após mudança: {amostra}")


def risk_row(risk: ChangeRisk, change, now: datetime) -> dict:
    return {
        "sha": risk.sha,
        "repo": change.repo,
        "author": change.author,
        "committed_at": change.committed_at,
        "total_score": risk.total,
        "band": risk.band,
        "blast_score": risk.blast.value,
        "blast_reason": risk.blast.reason,
        "history_score": risk.history.value,
        "history_reason": risk.history.reason,
        "size_score": risk.size.value,
        "size_reason": risk.size.reason,
        "provenance_score": risk.provenance.value,
        "provenance_reason": risk.provenance.reason,
        "assets": list(risk.assets),
        "contributors_json": json.dumps(list(risk.contributors), ensure_ascii=False),
        "computed_at": now,
        "policy_version": POLICY_VERSION,
    }


def load_secret_findings(spark: Any, settings: Settings) -> dict[str, list[dict]]:
    try:
        registros = store.query(
            spark,
            f"SELECT sha, pattern_name, severity FROM {settings.table('ops', 'secret_findings')}",
        )
    except Exception:
        return {}
    por_sha: dict[str, list[dict]] = {}
    for registro in registros:
        por_sha.setdefault(registro["sha"], []).append(registro)
    return por_sha


def apply_secrets(risk: ChangeRisk, findings: list[dict]) -> ChangeRisk:
    if not findings:
        return risk
    contribuidores = tuple(f"segredo: {f['pattern_name']} ({f['severity']})" for f in findings)
    banda = "alto" if any(f.get("severity") == "alta" for f in findings) else risk.band
    return replace(risk, band=banda, contributors=risk.contributors + contribuidores)


def build_rows(
    changes: list, sources: tuple[tuple[str, str], ...], edges: tuple, incidents: list[dict],
    weights: ChangeRiskWeights, now: datetime, settings: Settings,
    findings_by_sha: dict[str, list[dict]] | None = None,
) -> list[dict]:
    findings_by_sha = findings_by_sha or {}
    assets_por_change = {change.sha: assets_for(change.files, sources) for change in changes}
    changes_at_by_asset: dict[str, list[datetime]] = {}
    for change in changes:
        for ativo in assets_por_change[change.sha]:
            changes_at_by_asset.setdefault(ativo, []).append(change.committed_at)
    linhas: list[dict] = []
    for change in changes:
        assets = assets_por_change[change.sha]
        blast = blast_for(assets, edges, now, weights, settings)
        history = history_for(assets, incidents, changes_at_by_asset, weights)
        risco = score_change(change, blast, history, weights)
        risco = apply_secrets(risco, findings_by_sha.get(change.sha, []))
        linhas.append(risk_row(risco, change, now))
    return linhas


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(UTC)

    weights = load_weights(settings.change_risk_dir)
    changes = load_changes(spark, settings)
    if not changes:
        logger.info("sem mudanças em silver.changes; change_risk ignorado")
        return
    sources = load_registry(settings.metrics_dir).sources
    edges = lineage.load_graph(spark, settings)
    incidents = load_incident_assets(spark, settings)
    findings_by_sha = load_secret_findings(spark, settings)

    rows = build_rows(changes, sources, edges, incidents, weights, now, settings, findings_by_sha)
    store.replace_rows(spark, settings.table("ops", "change_risk"), rows)
    logger.info("change_risk pontuou %s mudança(s)", len(rows))


if __name__ == "__main__":
    main()
