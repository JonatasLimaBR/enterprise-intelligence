"""Monta a avaliação de risco de SLA de cada contrato e mantém o livro de previsões.

Roda dentro do `correlate`: precisa do histórico de runs (duração do produtor), dos regimes
(baseline vigente) e dos jobs monitorados (produtor e run em andamento).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from eict.adapters import schema_reader, store
from eict.config import Settings
from eict.domain import sla
from eict.domain.contracts import Contract
from eict.domain.models import Run
from eict.domain.producers import MonitoredJob, resolve
from eict.domain.regimes import Regime, regime_start

logger = logging.getLogger(__name__)

WRITES_LOOKBACK = timedelta(days=2)


@dataclass(frozen=True)
class SlaInput:
    """A avaliação mais urgente de cada ativo com SLO de freshness ou de entrega."""

    assessments: tuple[sla.Assessment, ...]


def load_monitored_jobs(spark: Any, settings: Settings) -> list[MonitoredJob]:
    try:
        records = store.query(spark, f"SELECT * FROM {settings.table('ops', 'monitored_jobs')}")
    except Exception as exc:
        logger.warning("jobs monitorados indisponíveis: %s", exc)
        return []
    return [
        MonitoredJob(
            job_id=record["job_id"],
            name=record.get("name") or "",
            active_run_id=record.get("active_run_id") or "",
            active_since=record.get("active_since"),
        )
        for record in records
    ]


def assess_contracts(
    spark: Any,
    contracts: list[Contract],
    history: list[Run],
    regimes: list[Regime],
    jobs: list[MonitoredJob],
    now: datetime,
) -> tuple[list[sla.Assessment], dict[str, list[datetime]]]:
    """Todas as avaliações (para o livro) e as escritas lidas por ativo (para o desfecho)."""
    avaliacoes: list[sla.Assessment] = []
    escritas_por_ativo: dict[str, list[datetime]] = {}
    for contract in contracts:
        slo = {chave: valor for chave, valor in contract.slo.items() if chave in (sla.FRESHNESS, sla.DELIVERY_TIME)}
        if not slo:
            continue
        try:
            ultima, _ = schema_reader.last_write_delay_seconds(spark, contract.asset)
            escritas = schema_reader.write_times(spark, contract.asset, now - WRITES_LOOKBACK)
        except schema_reader.SchemaUnavailableError as exc:
            logger.warning("SLA de %s não avaliado: %s", contract.asset, exc)
            continue
        escritas_por_ativo[contract.asset] = escritas

        resolucao = resolve(contract.producer, jobs)
        esperado = None
        motivo = resolucao.reason
        job_id = ""
        ativo_desde = None
        if resolucao.job is not None:
            job_id = resolucao.job.job_id
            ativo_desde = resolucao.job.active_since
            inicio = regime_start(job_id, regimes, history)
            esperado = sla.expected_duration(history, job_id, inicio)
            if esperado is None:
                motivo = "produtor sem 5 runs medidos no regime vigente"
        avaliacoes.extend(
            sla.assess(contract.asset, slo, ultima, escritas, now, esperado, job_id, ativo_desde, motivo)
        )
    return avaliacoes, escritas_por_ativo


def most_urgent_per_asset(assessments: list[sla.Assessment]) -> tuple[sla.Assessment, ...]:
    por_ativo: dict[str, list[sla.Assessment]] = {}
    for item in assessments:
        por_ativo.setdefault(item.asset, []).append(item)
    return tuple(sla.most_urgent(itens) for itens in por_ativo.values())


def record_predictions(spark: Any, settings: Settings, assessments: list[sla.Assessment], now: datetime) -> None:
    linhas = [
        store.sla_prediction_row(item, now, sla.POLICY_VERSION)
        for item in assessments
        if item.deadline is not None and item.klass != sla.VIOLADO
    ]
    if linhas:
        store.insert_missing(spark, settings.table("ops", "sla_predictions"), linhas, "prediction_id")


def settle_outcomes(
    spark: Any, settings: Settings, writes: dict[str, list[datetime]], now: datetime
) -> int:
    """Previsões cujo prazo já passou recebem o desfecho: houve escrita até o prazo?"""
    tabela = settings.table("ops", "sla_predictions")
    agora = now.isoformat(sep=" ", timespec="seconds")
    try:
        pendentes = store.query(
            spark,
            f"SELECT * FROM {tabela} WHERE outcome IS NULL AND deadline < TIMESTAMP '{agora}'",
        )
    except Exception as exc:
        logger.warning("livro de previsões indisponível: %s", exc)
        return 0
    linhas = []
    for record in pendentes:
        escritas = writes.get(record["asset"])
        if escritas is None:
            continue
        linhas.append(
            {
                **record,
                "outcome": sla.outcome(record["predicted_at"], record["deadline"], escritas),
                "outcome_at": now,
            }
        )
    if linhas:
        store.merge_rows(spark, tabela, linhas, ["prediction_id"])
    return len(linhas)


def build(
    spark: Any,
    settings: Settings,
    contracts: list[Contract],
    history: list[Run],
    regimes: list[Regime],
    now: datetime,
) -> SlaInput:
    avaliacoes, escritas = assess_contracts(
        spark, contracts, history, regimes, load_monitored_jobs(spark, settings), now
    )
    record_predictions(spark, settings, avaliacoes, now)
    settle_outcomes(spark, settings, escritas, now)
    return SlaInput(most_urgent_per_asset(avaliacoes))
