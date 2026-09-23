from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from eict.adapters import schema_reader
from eict.domain.contracts import Contract, Rule
from eict.domain.models import RuleResult, stable_id
from eict.domain.rules import (
    EVALUATION_ERROR,
    RuleCompilationError,
    compile_rule,
    conforming_columns,
    evaluate,
    evaluate_freshness,
    evaluate_schema,
    evaluate_volume,
)

logger = logging.getLogger(__name__)

MAX_ERROR_CHARS = 500


def run_rule(
    spark: Any,
    contract: Contract,
    rule: Rule,
    now: datetime,
    results_table: str | None = None,
) -> RuleResult:
    """Executa uma regra. Qualquer falha vira evaluation_error, nunca violação."""
    try:
        if rule.dimension == "schema":
            return _run_schema(spark, contract, rule, now)
        if rule.dimension == "freshness":
            return _run_freshness(spark, contract, rule, now)
        if rule.dimension == "volume":
            return _run_volume(spark, contract, rule, now, results_table)
        return _run_query(spark, contract, rule, now)
    except Exception as exc:
        logger.warning("regra %s falhou na execução: %s", rule.rule_id, exc)
        return _error(contract, rule, now, str(exc)[:MAX_ERROR_CHARS])


def run_contract(
    spark: Any, contract: Contract, now: datetime, results_table: str | None = None
) -> list[RuleResult]:
    return [run_rule(spark, contract, rule, now, results_table) for rule in contract.quality]


def _run_query(spark: Any, contract: Contract, rule: Rule, now: datetime) -> RuleResult:
    compiled = compile_rule(rule, contract)
    row = spark.sql(compiled.sql).first()
    numerator = int(row["numerator"] or 0)
    denominator = int(row["denominator"] or 0)
    return _result(
        contract,
        rule,
        now,
        status=evaluate(rule, numerator, denominator),
        query_hash=compiled.query_hash,
        numerator=numerator,
        denominator=denominator,
        sample=_as_sample(row["sample"] if "sample" in row.asDict() else None),
    )


def _run_freshness(spark: Any, contract: Contract, rule: Rule, now: datetime) -> RuleResult:
    compiled = compile_rule(rule, contract)
    _, delay = schema_reader.last_write_delay_seconds(spark, contract.asset)
    status, detail = evaluate_freshness(rule, delay)
    return _result(
        contract,
        rule,
        now,
        status=status,
        query_hash=compiled.query_hash,
        numerator=delay,
        denominator=0,
        detail=detail,
    )


def _run_volume(
    spark: Any, contract: Contract, rule: Rule, now: datetime, results_table: str | None
) -> RuleResult:
    compiled = compile_rule(rule, contract)
    row = spark.sql(compiled.sql).first()
    current = int(row["numerator"] or 0)
    history = (
        schema_reader.recent_row_counts(spark, results_table, rule.rule_id)
        if results_table
        else []
    )
    status, detail = evaluate_volume(rule, current, history)
    return _result(
        contract,
        rule,
        now,
        status=status,
        query_hash=compiled.query_hash,
        numerator=current,
        denominator=current,
        detail=detail,
    )


def _run_schema(spark: Any, contract: Contract, rule: Rule, now: datetime) -> RuleResult:
    actual = schema_reader.table_columns(spark, contract.asset)
    status, detail = evaluate_schema(contract.columns, actual)
    return _result(
        contract,
        rule,
        now,
        status=status,
        query_hash=stable_id("schema", contract.asset, ",".join(sorted(actual))),
        numerator=conforming_columns(contract.columns, actual),
        denominator=len(contract.columns),
        detail=detail,
    )


def _result(
    contract: Contract,
    rule: Rule,
    now: datetime,
    status: str,
    query_hash: str,
    numerator: int = 0,
    denominator: int = 0,
    sample: tuple[str, ...] = (),
    detail: str = "",
) -> RuleResult:
    return RuleResult(
        result_id=stable_id("res", contract.contract_id, rule.rule_id, now.isoformat()),
        contract_id=contract.contract_id,
        rule_id=rule.rule_id,
        asset=contract.asset,
        dimension=rule.dimension,
        status=status,
        threshold=rule.threshold,
        severity=rule.severity,
        window=rule.window,
        query_hash=query_hash,
        evaluated_at=now,
        numerator=numerator,
        denominator=denominator,
        sample=sample,
        detail=detail,
    )


def _error(contract: Contract, rule: Rule, now: datetime, message: str) -> RuleResult:
    try:
        query_hash = compile_rule(rule, contract).query_hash
    except RuleCompilationError:
        query_hash = ""
    return RuleResult(
        result_id=stable_id("res", contract.contract_id, rule.rule_id, now.isoformat()),
        contract_id=contract.contract_id,
        rule_id=rule.rule_id,
        asset=contract.asset,
        dimension=rule.dimension,
        status=EVALUATION_ERROR,
        threshold=rule.threshold,
        severity=rule.severity,
        window=rule.window,
        query_hash=query_hash,
        evaluated_at=now,
        error_message=message,
    )


def result_row(result: RuleResult) -> dict:
    return {
        "result_id": result.result_id,
        "contract_id": result.contract_id,
        "rule_id": result.rule_id,
        "asset": result.asset,
        "dimension": result.dimension,
        "status": result.status,
        "numerator": result.numerator,
        "denominator": result.denominator,
        "ratio": result.ratio,
        "threshold": result.threshold,
        "severity": result.severity,
        "window": result.window,
        "query_hash": result.query_hash,
        "sample_json": "[" + ",".join(result.sample) + "]" if result.sample else None,
        "error_message": result.error_message,
        "evaluated_at": result.evaluated_at,
    }


def _as_sample(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(str(item) for item in value if item is not None)
