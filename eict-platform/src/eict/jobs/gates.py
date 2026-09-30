"""Estágio `gates`: aplica a policy de gate sobre o change risk + findings (read-only).

Roda após `change_risk`. Grava um desfecho por sha em `ops.gate_decisions`. Não bloqueia nada externamente;
o override humano e o gate efetivo vivem no App.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from eict.adapters import store
from eict.adapters.gate_policy import load_policy
from eict.config import parse_settings
from eict.domain.gates import GateDecision, evaluate

logger = logging.getLogger(__name__)

POLICY_VERSION = "gate-v1"


def _query(spark: Any, sql: str) -> list[dict]:
    try:
        return store.query(spark, sql)
    except Exception:
        return []


def _by_sha(rows: list[dict]) -> dict[str, list[dict]]:
    grupos: dict[str, list[dict]] = {}
    for row in rows:
        grupos.setdefault(row.get("sha") or "", []).append(row)
    return grupos


def decision_row(decision: GateDecision, now: datetime) -> dict:
    return {
        "sha": decision.sha,
        "outcome": decision.outcome,
        "rule": decision.rule,
        "reason": decision.reason,
        "computed_at": now,
        "policy_version": POLICY_VERSION,
    }


def build_rows(change_risks: list[dict], secrets: dict, deps: dict, policy, now: datetime) -> list[dict]:
    linhas = []
    for change_risk in change_risks:
        sha = change_risk.get("sha") or ""
        decision = evaluate(change_risk, secrets.get(sha, []), deps.get(sha, []), policy)
        linhas.append(decision_row(decision, now))
    return linhas


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(UTC)

    policy = load_policy(settings.gates_dir)
    change_risks = _query(spark, f"SELECT sha, band FROM {settings.table('ops', 'change_risk')}")
    if not change_risks:
        logger.info("sem change_risk; gates ignorado")
        return
    secrets = _by_sha(_query(spark, f"SELECT sha, severity FROM {settings.table('ops', 'secret_findings')}"))
    deps = _by_sha(
        _query(
            spark,
            f"SELECT sha, severity FROM {settings.table('ops', 'dependency_findings')} "
            "WHERE sha IS NOT NULL AND sha <> ''",
        )
    )

    rows = build_rows(change_risks, secrets, deps, policy, now)
    store.replace_rows(spark, settings.table("ops", "gate_decisions"), rows)
    logger.info("gates: %s decisão(ões)", len(rows))


if __name__ == "__main__":
    main()
