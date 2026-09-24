from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from eict.adapters import capabilities as capability_probe
from eict.adapters import lineage, store
from eict.adapters.jira import label_for
from eict.config import Settings, parse_settings
from eict.domain import baseline as baseline_rules
from eict.domain import hypotheses as hypothesis_rules
from eict.domain import impact as impact_rules
from eict.domain.cost import BillingFact, incremental_cost
from eict.domain.incidents import RUNTIME_REGRESSION, Review, apply_reviews, detection_entry, open_or_update
from eict.domain.models import (
    ACTIVE_INCIDENT_STATES,
    CLOSED_INCIDENT_STATES,
    Change,
    Incident,
    RunFeatures,
    TimelineEntry,
)
from eict.domain.regimes import Regime, regime_start
from eict.domain.resolution import resolvable

logger = logging.getLogger(__name__)

CORRELATOR_CONNECTOR = "correlator"
CAUSAL_WINDOW = timedelta(days=7)
OUTBOX_PENDING = "pending"


def load_features(spark: Any, settings: Settings) -> list[RunFeatures]:
    records = store.query(
        spark,
        f"SELECT * FROM {settings.table('gold', 'run_features')} ORDER BY end_time",
    )
    return [RunFeatures(run=store.to_run(record), profile=store.to_run_profile(record)) for record in records]


def load_changes(spark: Any, settings: Settings) -> list[Change]:
    records = store.query(
        spark, f"SELECT * FROM {settings.table('silver', 'changes')} ORDER BY committed_at DESC"
    )
    return [
        Change(
            sha=record["sha"],
            repo=record.get("repo") or "",
            author=record.get("author") or "",
            committed_at=record["committed_at"],
            message=record.get("message") or "",
            files=tuple(record.get("files") or ()),
            patch=record.get("patch") or "",
        )
        for record in records
    ]


def load_active_incidents(spark: Any, settings: Settings) -> list[Incident]:
    states = ", ".join(f"'{state}'" for state in sorted(ACTIVE_INCIDENT_STATES))
    records = store.query(
        spark,
        f"SELECT * FROM {settings.table('ops', 'incidents')} WHERE state IN ({states})",
    )
    return [
        Incident(
            incident_id=record["incident_id"],
            correlation_key=record["correlation_key"],
            tenant_id=record["tenant_id"],
            subject=record["subject"],
            type=record["type"],
            state=record["state"],
            severity=record["severity"],
            first_run_id=record["first_run_id"],
            last_run_id=record["last_run_id"],
            detected_at=record["detected_at"],
            updated_at=record["updated_at"],
            affected_assets=tuple(record.get("affected_assets") or ()),
            ticket_refs=tuple(record.get("ticket_refs") or ()),
            declared_consumers=tuple(record.get("declared_consumers") or ()),
            version=int(record.get("version") or 1),
        )
        for record in records
    ]


def load_closed_until(spark: Any, settings: Settings) -> dict[str, datetime]:
    """Para cada job, o instante do último fechamento de um incidente de runtime."""
    states = ", ".join(f"'{state}'" for state in sorted(CLOSED_INCIDENT_STATES))
    records = store.query(
        spark,
        f"""
        SELECT subject, max(updated_at) AS fechado_em
        FROM {settings.table('ops', 'incidents')}
        WHERE type = '{RUNTIME_REGRESSION}' AND state IN ({states})
        GROUP BY subject
        """,
    )
    return {record["subject"]: record["fechado_em"] for record in records}


def load_regimes(spark: Any, settings: Settings) -> list[Regime]:
    """Aceites do console e declarações do repositório, já gravados, e as declarações do disco.

    As declarações válidas são gravadas a cada ciclo (id estável): assim o console mostra o
    histórico de marcos inteiro, venha de onde vier.
    """
    from eict.adapters import regime_loader

    diretorio = settings.baselines_dir or str(Path(__file__).resolve().parents[3] / "baselines")
    declaradas = regime_loader.load_directory(diretorio)
    for erro in declaradas.errors:
        logger.warning("declaração de regime recusada: %s", erro)
    if declaradas.regimes:
        store.merge_rows(
            spark,
            settings.table("ops", "baseline_regimes"),
            [store.regime_row(regime) for regime in declaradas.regimes],
            ["regime_id"],
        )
    records = store.query(spark, f"SELECT * FROM {settings.table('ops', 'baseline_regimes')}")
    return [store.to_regime(record) for record in records]


def load_reviews(spark: Any, settings: Settings) -> list[Review]:
    records = store.query(spark, f"SELECT * FROM {settings.table('ops', 'hypothesis_reviews')}")
    return [
        Review(
            hypothesis_id=record["hypothesis_id"],
            decision=record["decision"],
            reviewer=record["reviewer"],
            at=record["at"],
            note=record.get("note") or "",
        )
        for record in records
    ]


def changes_in_window(changes: list[Change], healthy: RunFeatures | None, current: RunFeatures) -> list[Change]:
    window_start = healthy.run.end_time if healthy else current.run.start_time - CAUSAL_WINDOW
    in_window = [
        change
        for change in changes
        if window_start <= change.committed_at <= current.run.start_time
    ]
    deployed = [change for change in changes if change.sha == current.run.git_sha]
    ordered = deployed + [change for change in in_window if change.sha not in {c.sha for c in deployed}]
    return ordered


def lineage_ready(capabilities: list) -> bool:
    return capability_probe.status_of(capabilities, capability_probe.TABLE_LINEAGE)


def refresh_graph(spark: Any, settings: Settings, available: bool, now: datetime) -> tuple:
    """Atualiza o grafo acumulado e devolve as arestas para percorrer.

    O grafo materializado é a fonte da travessia, não a consulta do ciclo: arestas
    vistas em ciclos anteriores continuam valendo, com o peso que a recência lhes der.
    """
    observations = lineage.fetch_edges(spark, settings, available)
    if observations:
        lineage.merge_graph(
            spark, settings, observations, lineage.schema_fingerprints(spark, settings), now
        )
    return lineage.load_graph(spark, settings) if available else ()


def impact_for(
    edges: tuple, subject: str, settings: Settings, now: datetime
) -> impact_rules.ImpactResult:
    return impact_rules.traverse(
        edges,
        subject,
        now,
        direction=impact_rules.DOWNSTREAM,
        max_depth=settings.impact_max_depth,
        excluded=settings.excluded_assets,
    )


def apply_impact(incident: Incident, result: impact_rules.ImpactResult) -> Incident:
    """Grava o raio e eleva a severidade quando ele alcança consumo humano."""
    if not result.nodes:
        return incident
    subida = impact_rules.escalation(incident.severity, result)
    return incident.with_impact(
        assets=result.assets,
        score=result.score,
        policy_version=result.policy_version,
        severity=subida.to_severity if subida else None,
        escalation_reason=subida.reason if subida else "",
    )


def billing_facts(
    spark: Any, run_ids: list[str], available: bool
) -> dict[str, BillingFact]:
    """Custo de todos os runs numa consulta só.

    Uma consulta por run custava ~170s por ciclo: seis por incidente, cada uma com join
    entre usage e list_prices sobre a tabela de faturamento inteira.
    """
    if not available or not run_ids:
        return {}
    lista = ", ".join(f"'{run_id}'" for run_id in sorted(set(run_ids)))
    try:
        records = store.query(
            spark,
            f"""
            SELECT u.usage_metadata.job_run_id AS run_id,
                   SUM(u.usage_quantity) AS dbus,
                   SUM(u.usage_quantity * p.pricing.default) AS list_cost_usd
            FROM {capability_probe.BILLING_USAGE} u
            JOIN {capability_probe.BILLING_PRICES} p
              ON u.sku_name = p.sku_name AND p.price_end_time IS NULL
            WHERE u.usage_metadata.job_run_id IN ({lista})
            GROUP BY u.usage_metadata.job_run_id
            """,
        )
    except Exception as exc:
        logger.warning("consulta de billing falhou: %s", exc)
        return {}

    return {
        record["run_id"]: BillingFact(
            run_id=record["run_id"],
            dbus=float(record["dbus"]),
            list_cost_usd=float(record["list_cost_usd"] or 0.0),
            source_ref=capability_probe.BILLING_USAGE,
        )
        for record in records
        if record.get("dbus") is not None
    }


def correlate(
    spark: Any,
    settings: Settings,
    features: list[RunFeatures],
    changes: list[Change],
    incidents: list[Incident],
    reviews: list[Review],
    capabilities: list[capability_probe.Capability],
    now: datetime,
    graph: tuple = (),
    closed_until: dict[str, datetime] | None = None,
    regimes: list[Regime] | tuple[Regime, ...] = (),
) -> list[Incident]:
    """Reavalia o histórico inteiro a cada ciclo — por isso precisa de `closed_until`.

    Um run lento anterior ao fechamento do incidente do seu job já foi julgado. Sem esse
    corte, o incidente fechado renasceria no ciclo seguinte com a mesma chave, porque o
    run que o abriu continua no histórico e continua lento. O run julgado segue fora do
    baseline: fechar o incidente não o torna saudável.
    """
    closed_until = closed_until or {}
    history = [item.run for item in features]
    inicios = {
        job_id: regime_start(job_id, list(regimes), history)
        for job_id in {run.job_id for run in history}
    }
    by_run_id = {item.run_id: item for item in features}
    billing_available = capability_probe.status_of(capabilities, capability_probe.BILLING_USAGE)
    touched: list[Incident] = []
    incident_run_ids = _runs_under_incident(incidents)
    latest: dict[str, tuple[RunFeatures, bool]] = {}

    for current in features:
        verdict = baseline_rules.evaluate(
            current.run, history, incident_run_ids, inicios.get(current.run.job_id)
        )
        fechado_em = closed_until.get(current.run.job_id)
        if fechado_em is not None and current.run.end_time <= fechado_em:
            if verdict.is_regression:
                incident_run_ids = incident_run_ids | {current.run_id}
            continue
        if verdict.baseline is not None:
            latest[current.run.job_id] = (current, verdict.is_regression)
        if not verdict.is_regression or verdict.baseline is None:
            incident_run_ids = incident_run_ids - {current.run_id}
            continue

        incident, created = open_or_update(
            incidents, settings.tenant_id, current.run.job_id, RUNTIME_REGRESSION, current.run
        )
        incident_run_ids = incident_run_ids | {current.run_id}
        healthy_run = baseline_rules.last_healthy_run(history, current.run, incident_run_ids)
        healthy = by_run_id.get(healthy_run.run_id) if healthy_run else None
        analysis = hypothesis_rules.analyze(
            current,
            healthy,
            changes_in_window(changes, healthy, current),
            now,
            scope_id=incident.incident_id,
        )
        reviewed, review_entries = apply_reviews(list(analysis.hypotheses), reviews)

        incident = apply_impact(
            incident, impact_for(graph, current.run.job_id, settings, now)
        )

        _persist_incident(
            spark, settings, incident, current.run, verdict.baseline, created, analysis, reviewed, review_entries
        )
        _persist_cost(
            spark, settings, incident, current, history, billing_available, now
        )
        _queue_ticket(spark, settings, incident, current, reviewed, now)

        incidents = [item for item in incidents if item.correlation_key != incident.correlation_key]
        incidents.append(incident)
        touched.append(incident)

    for incident, entry in resolvable(incidents, *runtime_state(latest), now):
        _persist_resolution(spark, settings, incident, entry)
        touched.append(incident)

    return touched


def runtime_state(
    latest: dict[str, tuple[RunFeatures, bool]],
) -> tuple[frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
    """Jobs avaliados e jobs regredidos, pelo run mais recente de cada um.

    Avaliado exige baseline e sucesso: run sem histórico suficiente não prova nada, e run
    que falhou pode ser curto por ter morrido cedo — duração dentro do baseline não é
    recuperação.
    """
    avaliados: set[tuple[str, str]] = set()
    violando: set[tuple[str, str]] = set()
    for job_id, (current, regressed) in latest.items():
        if regressed:
            violando.add((job_id, RUNTIME_REGRESSION))
        if current.run.succeeded:
            avaliados.add((job_id, RUNTIME_REGRESSION))
    return frozenset(avaliados), frozenset(violando)


def _persist_resolution(spark, settings, incident: Incident, entry: TimelineEntry) -> None:
    store.merge_rows(
        spark, settings.table("ops", "incidents"), [store.incident_row(incident)], ["correlation_key"]
    )
    store.insert_missing(
        spark, settings.table("ops", "incident_timeline"), [store.timeline_row(entry)], "entry_id"
    )


def _runs_under_incident(incidents: list[Incident]) -> frozenset[str]:
    attributed: set[str] = set()
    for incident in incidents:
        if incident.is_active:
            attributed.update({incident.first_run_id, incident.last_run_id})
    return frozenset(attributed)


def _persist_incident(
    spark, settings, incident, run, baseline, created, analysis, hypotheses, review_entries
) -> None:
    store.merge_rows(
        spark, settings.table("ops", "incidents"), [store.incident_row(incident)], ["correlation_key"]
    )
    store.insert_missing(
        spark,
        settings.table("ops", "evidence"),
        [store.evidence_row(incident.incident_id, item) for item in analysis.evidence],
        "evidence_id",
    )
    store.merge_rows(
        spark,
        settings.table("ops", "hypotheses"),
        [store.hypothesis_row(incident.incident_id, item) for item in hypotheses],
        ["hypothesis_id"],
    )
    entries = [detection_entry(incident, run, baseline, created), *review_entries]
    store.insert_missing(
        spark,
        settings.table("ops", "incident_timeline"),
        [store.timeline_row(entry) for entry in entries],
        "entry_id",
    )


def _persist_cost(spark, settings, incident, current, history, billing_available, now) -> None:
    baseline_runs = [
        run for run in history if run.succeeded and run.end_time < current.run.start_time
    ][-5:]
    custos = billing_facts(
        spark,
        [run.run_id for run in baseline_runs] + [current.run_id],
        billing_available,
    )
    cost = incremental_cost(
        run_id=current.run_id,
        run_end=current.run.end_time,
        now=now,
        run_fact=custos.get(current.run_id),
        baseline_facts=[custos[run.run_id] for run in baseline_runs if run.run_id in custos],
        billing_available=billing_available,
    )
    store.merge_rows(
        spark,
        settings.table("ops", "run_cost"),
        [
            {
                "run_id": cost.run_id,
                "incident_id": incident.incident_id,
                "status": cost.status,
                "dbus": cost.dbus,
                "list_cost_usd": cost.list_cost_usd,
                "baseline_cost_usd": cost.baseline_cost_usd,
                "incremental_cost_usd": cost.incremental_cost_usd,
                "source_ref": cost.source_ref,
                "updated_at": now,
            }
        ],
        ["run_id"],
    )


def _queue_ticket(spark, settings, incident, current, hypotheses, now) -> None:
    if not settings.jira_base_url or not settings.jira_project:
        return
    top = min(hypotheses, key=lambda item: item.rank) if hypotheses else None
    summary = f"[EICT] Regressão de runtime no job {incident.job_id}"
    description = json.dumps(
        {
            "incident_id": incident.incident_id,
            "correlation_key": incident.correlation_key,
            "run_id": current.run_id,
            "duration_s": current.run.duration_s,
            "execution_s": current.run.execution_s,
            "top_hypothesis": top.statement if top else None,
            "confidence": top.confidence if top else None,
            "affected_assets": list(incident.affected_assets),
        },
        ensure_ascii=False,
        indent=2,
    )
    store.insert_missing(
        spark,
        settings.table("ops", "ticket_outbox"),
        [
            {
                "correlation_key": incident.correlation_key,
                "incident_id": incident.incident_id,
                "status": OUTBOX_PENDING,
                "attempts": 0,
                "next_attempt_at": now,
                "last_error": None,
                "issue_key": None,
                "issue_url": None,
                "summary": summary,
                "description": f"{description}\n\nlabel: {label_for(incident.correlation_key)}",
                "updated_at": now,
            }
        ],
        "correlation_key",
    )


PRODUCER_WINDOW_HOURS = 6


def producer_states(spark, settings, producers: set[str], now) -> dict[str, bool]:
    """Para cada produtor declarado, diz se ele rodou com sucesso na janela recente.

    Sem isso, a hipótese de pipeline parado nunca pontua — e ela costuma ser a resposta
    certa quando a violação é de freshness.
    """
    if not producers:
        return {}
    from eict.jobs.sla_risk import load_monitored_jobs

    limite = (now - timedelta(hours=PRODUCER_WINDOW_HOURS)).isoformat(sep=" ", timespec="seconds")
    try:
        records = store.query(
            spark,
            f"""
            SELECT job_id, max_by(result_state, end_time) AS estado
            FROM {settings.table('gold', 'run_features')}
            WHERE end_time >= TIMESTAMP '{limite}'
            GROUP BY job_id
            """,
        )
    except Exception as exc:
        logger.warning("estado dos produtores indisponível: %s", exc)
        return {}
    return states_by_producer(producers, load_monitored_jobs(spark, settings), records)


def states_by_producer(producers: set[str], jobs: list, records: list[dict]) -> dict[str, bool]:
    """Produtor → último run na janela terminou com sucesso?

    Resolve o produtor por nome exato e compara por `job_id`. Casar por substring do
    `job_name` fazia o produtor do painel comercial herdar o estado do job pequeno, e deixava
    de fora os runs antigos, que não têm nome gravado.
    """
    from eict.domain.producers import resolve

    por_job = {str(record["job_id"]): record["estado"] for record in records}
    estados: dict[str, bool] = {}
    for producer in producers:
        resolucao = resolve(producer, jobs)
        if resolucao.job is None:
            continue
        estados[producer] = por_job.get(resolucao.job.job_id) == "SUCCESS"
    return estados


def correlate_quality_incidents(
    spark, settings, incidents, changes, now, graph=(), history=(), regimes=()
) -> int:
    """Roda o correlator de qualidade sobre os resultados de regra recentes."""
    from eict.adapters.contract_loader import load_directory
    from eict.jobs import correlate_quality as quality_correlator
    from eict.jobs import sla_risk
    from eict.jobs.quality import contracts_dir

    contracts = {
        contract.asset: contract for contract in load_directory(contracts_dir(settings)).active
    }
    results = quality_correlator.load_recent_results(spark, settings, now)
    semantics = quality_correlator.load_semantic_state(spark, settings, now)
    try:
        sla_input = sla_risk.build(spark, settings, list(contracts.values()), list(history), list(regimes), now)
    except Exception as exc:
        logger.warning("risco de SLA não avaliado neste ciclo: %s", exc)
        sla_input = None
    if not results and semantics is None and sla_input is None:
        return 0
    payload = quality_correlator.QualityInput(
        results=results,
        contracts=contracts,
        changes=changes,
        producer_states=producer_states(
            spark, settings, {contract.producer for contract in contracts.values()}, now
        ),
        graph=graph,
        changed_upstream=lineage.changed_assets(spark, settings) if graph else frozenset(),
        max_depth=settings.impact_max_depth,
        excluded=settings.excluded_assets,
        semantics=semantics,
        sla=sla_input.assessments if sla_input is not None else None,
    )
    touched, entries, evidences, hypotheses = quality_correlator.correlate_quality(
        payload, incidents, settings.tenant_id, now
    )
    quality_correlator.persist(spark, settings, touched, entries, evidences, hypotheses)
    return len(touched)


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    from eict.jobs.bootstrap_ops import ensure_gold_view

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    ensure_gold_view(spark, settings)
    now = datetime.now(UTC)
    capabilities = [
        capability_probe.Capability(
            capability=record["capability"],
            status=record["status"],
            detail=record.get("detail") or "",
            checked_at=record["checked_at"],
        )
        for record in store.query(spark, f"SELECT * FROM {settings.table('ops', 'capabilities')}")
    ]
    changes = load_changes(spark, settings)
    graph = refresh_graph(spark, settings, lineage_ready(capabilities), now)
    features = load_features(spark, settings)
    regimes = load_regimes(spark, settings)
    touched = correlate(
        spark,
        settings,
        features,
        changes,
        load_active_incidents(spark, settings),
        load_reviews(spark, settings),
        capabilities,
        now,
        graph,
        load_closed_until(spark, settings),
        regimes,
    )
    quality_touched = correlate_quality_incidents(
        spark,
        settings,
        load_active_incidents(spark, settings),
        changes,
        now,
        graph,
        [item.run for item in features],
        regimes,
    )
    logger.info(
        "correlacionados: %s incidentes de runtime, %s de qualidade",
        len(touched),
        quality_touched,
    )


if __name__ == "__main__":
    main()
