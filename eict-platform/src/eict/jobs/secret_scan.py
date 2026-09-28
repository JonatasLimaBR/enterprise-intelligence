"""Estágio `secret_scan`: varre segredos nos commits de `silver.changes` (read-only).

Roda antes do `change_risk`, que consome `ops.secret_findings` para aplicar piso de banda e contribuidores.
Nunca grava o valor cru do segredo — só o trecho mascarado.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from eict.adapters import store
from eict.adapters.secret_patterns import load_policy
from eict.config import parse_settings
from eict.domain.secret_scan import SecretFinding
from eict.domain.secret_scan import scan as scan_change
from eict.jobs.correlate import load_changes

logger = logging.getLogger(__name__)

POLICY_VERSION = "secret-scan-v1"


def finding_row(finding: SecretFinding, now: datetime) -> dict:
    return {
        "sha": finding.sha,
        "file": finding.file,
        "line": finding.line,
        "pattern_name": finding.pattern_name,
        "severity": finding.severity,
        "masked": finding.masked,
        "computed_at": now,
        "policy_version": POLICY_VERSION,
    }


def build_rows(changes: list, policy, now: datetime) -> list[dict]:
    linhas: list[dict] = []
    for change in changes:
        for finding in scan_change(change, policy):
            linhas.append(finding_row(finding, now))
    return linhas


def main(argv: list[str] | None = None) -> None:
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(UTC)

    policy = load_policy(settings.secret_scan_dir)
    changes = load_changes(spark, settings)
    rows = build_rows(changes, policy, now)
    store.replace_rows(spark, settings.table("ops", "secret_findings"), rows)
    logger.info("secret_scan: %s finding(s) em %s mudança(s)", len(rows), len(changes))


if __name__ == "__main__":
    main()
