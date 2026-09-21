from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eict.adapters import rule_runner, store
from eict.adapters.contract_loader import load_directory
from eict.config import Settings, parse_settings
from eict.domain.contracts import Contract, summary_row
from eict.domain.models import RuleResult

logger = logging.getLogger(__name__)

CONTRACTS_DIRNAME = "contracts"
DLQ_SOURCE = "contract_loader"


def contracts_dir(settings: Settings) -> Path:
    """No bundle, os contratos ficam ao lado do wheel; em teste, na raiz do repositório."""
    if settings.contracts_dir:
        return Path(settings.contracts_dir)
    return Path(__file__).resolve().parents[4] / CONTRACTS_DIRNAME


def evaluate_contracts(
    spark: Any, contracts: tuple[Contract, ...], now: datetime, results_table: str
) -> list[RuleResult]:
    results: list[RuleResult] = []
    for contract in contracts:
        contract_results = rule_runner.run_contract(spark, contract, now, results_table)
        results.extend(contract_results)
        logger.info(
            "contrato %s: %s regras, %s violações, %s erros",
            contract.contract_id,
            len(contract_results),
            sum(1 for item in contract_results if item.is_violation),
            sum(1 for item in contract_results if item.is_error),
        )
    return results


def persist(spark: Any, settings: Settings, contracts, results, now: datetime) -> None:
    store.append_rows(
        spark,
        settings.table("ops", "rule_results"),
        [rule_runner.result_row(result) for result in results],
    )
    store.merge_rows(
        spark,
        settings.table("ops", "contracts"),
        [summary_row(contract, now) for contract in contracts],
        ["contract_id"],
    )


def record_load_errors(spark: Any, settings: Settings, errors: tuple[str, ...], now) -> None:
    if not errors:
        return
    store.append_rows(
        spark,
        settings.table("ops", "dlq"),
        [
            {
                "dlq_id": f"contract-{index}-{now:%Y%m%d%H%M%S}",
                "source": DLQ_SOURCE,
                "payload": message[:200],
                "error": message[:500],
                "at": now,
            }
            for index, message in enumerate(errors)
        ],
    )


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(UTC)

    outcome = load_directory(contracts_dir(settings))
    record_load_errors(spark, settings, outcome.errors, now)
    if not outcome.active:
        logger.warning("nenhum contrato ativo em %s", contracts_dir(settings))
        return

    results = evaluate_contracts(
        spark, outcome.active, now, settings.table("ops", "rule_results")
    )
    persist(spark, settings, outcome.active, results, now)

    violations = [item for item in results if item.is_violation]
    errors = [item for item in results if item.is_error]
    logger.info(
        "qualidade avaliada: %s regras, %s violações, %s erros de execução",
        len(results),
        len(violations),
        len(errors),
    )


if __name__ == "__main__":
    main()
