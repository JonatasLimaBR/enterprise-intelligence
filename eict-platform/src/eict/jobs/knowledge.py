"""Monta os read models de runbooks e conhecimento no fim do correlate.

Tudo é calculado antes de qualquer escrita: se algo falhar no meio, os read models do ciclo
anterior ficam intactos, em vez de o console mostrar metade substituída.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from eict.adapters import runbook_loader, store
from eict.config import Settings
from eict.domain import knowledge, problems
from eict.domain.runbooks import Runbook, applicable

logger = logging.getLogger(__name__)

ACTIVE_STATES = ("detected", "triaged", "investigating", "mitigating", "monitoring")


def runbooks_dir(settings: Settings) -> Path:
    if settings.runbooks_dir:
        return Path(settings.runbooks_dir)
    return Path(__file__).resolve().parents[3] / "runbooks"


def violation_dimensions(evidence_rows: list[dict]) -> dict[str, frozenset[str]]:
    """Dimensões das regras violadas, por incidente, lidas da evidência `rule_violation`."""
    por_incidente: dict[str, set[str]] = {}
    for row in evidence_rows:
        if row.get("kind") != "rule_violation":
            continue
        try:
            dimensao = json.loads(row.get("value") or "{}").get("dimension")
        except (TypeError, ValueError):
            continue
        if dimensao:
            por_incidente.setdefault(row["incident_id"], set()).add(dimensao)
    return {incident_id: frozenset(dims) for incident_id, dims in por_incidente.items()}


def build_rows(
    runbooks: list[Runbook],
    incidents: list[dict],
    causes: dict[str, str],
    dimensions: dict[str, frozenset[str]],
    usages: list[dict],
    candidates: list[dict],
    records: dict[str, dict],
    now: datetime,
) -> dict[str, list[dict]]:
    """Todas as linhas dos read models, puro. Chave = nome da tabela em `ops`."""
    ativos = [item for item in incidents if item["state"] in ACTIVE_STATES]
    por_id = {item["incident_id"]: item for item in incidents}
    resolvidos = {
        item["signature"]: records[item["problem_id"]]
        for item in candidates
        if item.get("status") == problems.RESOLVIDO and item["problem_id"] in records
    }

    incident_runbooks, similares = [], []
    for incidente in ativos:
        causa = causes.get(incidente["incident_id"], problems.NO_HYPOTHESIS)
        dims = dimensions.get(incidente["incident_id"], frozenset())
        for item in applicable(runbooks, incidente["type"], causa, dims):
            incident_runbooks.append(
                {
                    "incident_id": incidente["incident_id"],
                    "runbook_id": item.runbook.runbook_id,
                    "level": item.level,
                    "reason": item.reason,
                    "status": item.runbook.status,
                    "evaluated_at": now,
                }
            )
        for item in knowledge.similar(incidente, incidents, causes, now):
            outro = por_id[item.similar_id]
            aprendido = resolvidos.get(
                problems.signature(outro, causes.get(outro["incident_id"], problems.NO_HYPOTHESIS)), {}
            )
            similares.append(
                {
                    "incident_id": item.incident_id,
                    "similar_id": item.similar_id,
                    "level": item.level,
                    "reason": item.reason,
                    "similar_subject": item.subject,
                    "similar_state": item.state,
                    "hours_to_recover": item.hours_to_recover,
                    "known_error": aprendido.get("known_error"),
                    "workaround": aprendido.get("workaround"),
                    "fix_description": aprendido.get("fix_description"),
                    "rank": item.rank,
                    "evaluated_at": now,
                }
            )

    eficacia = [
        {
            "runbook_id": item.runbook_id,
            "uses": item.uses,
            "successes": item.successes,
            "failures": item.failures,
            "pending": item.pending,
            "efficacy": item.efficacy,
            "median_hours_to_recover": item.median_hours_to_recover,
            "small_sample": item.small_sample,
            "evaluated_at": now,
        }
        for item in knowledge.efficacy(usages, por_id, now)
    ]

    conhecimento = []
    for candidato in candidates:
        registro = records.get(candidato["problem_id"])
        if registro is None:
            continue
        tipo, _, causa = candidato["signature"].split("|", 2)
        escolhidos = applicable(runbooks, tipo, causa)
        item = knowledge.knowledge_item(candidato, registro, escolhidos[0].runbook.runbook_id if escolhidos else "")
        if item is not None:
            conhecimento.append({**item.__dict__, "evaluated_at": now})

    catalogo = [
        {
            "runbook_id": item.runbook_id,
            "title": item.title,
            "status": item.status,
            "owner": item.owner,
            "incident_types": list(item.incident_types),
            "hypothesis_codes": list(item.hypothesis_codes),
            "dimensions": list(item.dimensions),
            "steps": list(item.steps),
            "connector": item.connector,
            "source_file": item.source_file,
            "loaded_at": now,
        }
        for item in runbooks
    ]
    return {
        "runbooks": catalogo,
        "incident_runbooks": incident_runbooks,
        "similar_incidents": similares,
        "runbook_efficacy": eficacia,
        "knowledge_items": conhecimento,
    }


def refresh(spark: Any, settings: Settings, now: datetime) -> dict[str, int]:
    from eict.jobs.correlate import reviewed_hypotheses

    carga = runbook_loader.load_directory(runbooks_dir(settings))
    for erro in carga.errors:
        logger.warning("runbook recusado: %s", erro)
    incidentes = store.query(spark, f"SELECT * FROM {settings.table('ops', 'incidents')}")
    causas = {
        incident_id: problems.top_cause(hipoteses)
        for incident_id, hipoteses in reviewed_hypotheses(spark, settings).items()
    }
    evidencias = store.query(
        spark, f"SELECT incident_id, kind, value FROM {settings.table('ops', 'evidence')} WHERE kind = 'rule_violation'"
    )
    usos = store.query(spark, f"SELECT * FROM {settings.table('ops', 'runbook_usage')}")
    candidatos = store.query(spark, f"SELECT * FROM {settings.table('ops', 'problem_candidates')}")
    registros = {
        record["problem_id"]: record
        for record in store.query(spark, f"SELECT * FROM {settings.table('ops', 'problem_records')}")
    }
    linhas = build_rows(
        list(carga.runbooks), incidentes, causas, violation_dimensions(evidencias), usos, candidatos, registros, now
    )
    return {tabela: store.replace_rows(spark, settings.table("ops", tabela), rows) for tabela, rows in linhas.items()}
