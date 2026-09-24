"""Regressão de custo por run: custo subiu sem o tempo de execução subir.

O núcleo (`correlate_costs`) é puro para ser testado sem Spark; `run` faz a E/S. Reavalia a
história inteira a cada ciclo, como o correlator de runtime — e herda dele as duas lições:
incidente fechado não renasce do mesmo run antigo (`closed_until`), e o run julgado como
regressão fica fora do baseline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import datetime
from typing import Any

from eict.adapters import capabilities as capability_probe
from eict.adapters import store
from eict.config import Settings
from eict.domain import baseline as runtime_rules
from eict.domain import cost_baseline
from eict.domain.incidents import COST_REGRESSION, open_or_update
from eict.domain.models import Evidence, Incident, RunFeatures, TimelineEntry
from eict.domain.regimes import Regime, regime_start
from eict.domain.resolution import resolvable

logger = logging.getLogger(__name__)

SEVERITY = "warning"


def correlate_costs(
    features: list[RunFeatures],
    incidents: list[Incident],
    costs: dict[str, float],
    regimes: list[Regime],
    closed_until: dict[str, datetime],
    tenant_id: str,
    now: datetime,
) -> tuple[list[Incident], list[TimelineEntry], list[tuple[str, Evidence]]]:
    history = [item.run for item in features]
    inicios = {job: regime_start(job, regimes, history) for job in {run.job_id for run in history}}
    em_incidente = _runs_under(incidents)
    incidentes = list(incidents)
    touched: list[Incident] = []
    entries: list[TimelineEntry] = []
    evidences: list[tuple[str, Evidence]] = []
    ultimo: dict[str, tuple[bool, bool]] = {}   # job → (avaliado, regrediu)

    for item in sorted(features, key=lambda feature: feature.run.end_time):
        run = item.run
        inicio = inicios.get(run.job_id)
        veredito = cost_baseline.evaluate(run, history, costs, em_incidente, inicio)
        fechado_em = closed_until.get(run.job_id)
        if fechado_em is not None and run.end_time <= fechado_em:
            if veredito.is_regression:
                em_incidente = em_incidente | {run.run_id}
            continue
        if veredito.baseline is not None:
            ultimo[run.job_id] = (run.succeeded, veredito.is_regression)
        if not veredito.is_regression:
            continue

        # O tempo também regrediu? Então o incidente de runtime já carrega o custo.
        runtime = runtime_rules.evaluate(run, history, em_incidente, inicio)
        em_incidente = em_incidente | {run.run_id}
        if runtime.is_regression:
            continue

        incidente, criado = open_or_update(incidentes, tenant_id, run.job_id, COST_REGRESSION, run)
        if criado:
            incidente = replace(incidente, severity=SEVERITY)
        razao = (
            runtime.value_s / runtime.baseline.median_s
            if runtime.baseline is not None and runtime.baseline.median_s
            else None
        )
        resumo = cost_baseline.summary(run, veredito, razao)
        evidencia = Evidence.create(
            kind="cost_regression",
            source_ref=f"billing/{run.job_id}/{run.run_id}",
            observed_at=now,
            summary=resumo,
            value=json.dumps(
                {
                    "cost_usd": veredito.cost_usd,
                    "median_usd": veredito.baseline.median_usd,
                    "mad_usd": veredito.baseline.mad_usd,
                    "threshold_usd": veredito.baseline.threshold_usd,
                    "deciding_term": veredito.baseline.deciding_term,
                    "n": veredito.baseline.n,
                    "execution_ratio": razao,
                    "env_hash": run.env_hash,
                    "policy_version": cost_baseline.POLICY_VERSION,
                },
                ensure_ascii=False,
            ),
        )
        entries.append(
            TimelineEntry.create(
                incident_id=incidente.incident_id,
                at=run.end_time,
                kind="detected" if criado else "recurrence",
                summary=resumo,
                evidence_ids=(evidencia.evidence_id,),
            )
        )
        evidences.append((incidente.incident_id, evidencia))
        incidentes = [inc for inc in incidentes if inc.correlation_key != incidente.correlation_key]
        incidentes.append(incidente)
        touched.append(incidente)

    avaliados = frozenset((job, COST_REGRESSION) for job, (ok, _) in ultimo.items() if ok)
    violando = frozenset((job, COST_REGRESSION) for job, (_, regrediu) in ultimo.items() if regrediu)
    for incidente, entrada in resolvable(incidentes, avaliados, violando, now):
        entries.append(entrada)
        touched.append(incidente)
    return touched, entries, evidences


def _runs_under(incidents: list[Incident]) -> frozenset[str]:
    return frozenset(
        run_id
        for incident in incidents
        if incident.is_active
        for run_id in (incident.first_run_id, incident.last_run_id)
    )


def run(
    spark: Any,
    settings: Settings,
    features: list[RunFeatures],
    incidents: list[Incident],
    capabilities: list,
    regimes: list[Regime],
    closed_until: dict[str, datetime],
    now: datetime,
) -> int:
    from eict.jobs.correlate import billing_facts

    disponivel = capability_probe.status_of(capabilities, capability_probe.BILLING_USAGE)
    fatos = billing_facts(spark, [item.run_id for item in features], disponivel)
    custos = {run_id: fato.list_cost_usd for run_id, fato in fatos.items()}
    if not custos:
        return 0
    custo_incidentes = [item for item in incidents if item.type == COST_REGRESSION]
    touched, entries, evidences = correlate_costs(
        features, custo_incidentes, custos, regimes, closed_until, settings.tenant_id, now
    )
    if touched:
        store.merge_rows(
            spark, settings.table("ops", "incidents"), [store.incident_row(item) for item in touched],
            ["correlation_key"],
        )
    if evidences:
        store.insert_missing(
            spark, settings.table("ops", "evidence"),
            [store.evidence_row(incident_id, item) for incident_id, item in evidences], "evidence_id",
        )
    if entries:
        store.insert_missing(
            spark, settings.table("ops", "incident_timeline"),
            [store.timeline_row(item) for item in entries], "entry_id",
        )
    return len(touched)
