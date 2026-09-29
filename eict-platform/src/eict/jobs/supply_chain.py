"""Estágio `supply_chain`: SBOM das dependências + matching de advisories (read-only).

Roda antes do `change_risk`, que consome `ops.dependency_findings` (findings com `sha`). Materializa o
SBOM dos manifestos do repo monitorado via GitHub; falha ao buscar → SBOM vazio, ciclo segue.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from eict.adapters import store
from eict.adapters.advisory_catalog import load_advisories
from eict.adapters.github import GitHubClient, GitHubError
from eict.config import Settings, parse_settings
from eict.domain.supply_chain import Advisory, DependencyFinding, match, parse_dependencies, scan_change
from eict.jobs.correlate import load_changes

logger = logging.getLogger(__name__)

POLICY_VERSION = "supply-chain-v1"
MANIFESTS = ("pyproject.toml", "app/requirements.txt")


def monitored_repo(settings: Settings) -> str:
    return settings.workload_repo or settings.github_repo


def github_client(workspace: Any, settings: Settings) -> GitHubClient | None:
    repo = monitored_repo(settings)
    if not repo:
        return None
    try:
        token = workspace.dbutils.secrets.get(settings.secret_scope, "github_token")
    except Exception:
        token = ""
    return GitHubClient(repo=repo, token=token)


def build_sbom(client: GitHubClient | None) -> list[tuple[str, str, str]]:
    """(pacote, versão declarada, arquivo) dos manifestos do repo; falha → lista vazia."""
    if client is None:
        return []
    inventario: list[tuple[str, str, str]] = []
    for caminho in MANIFESTS:
        try:
            texto = client.fetch_file(caminho)
        except GitHubError as exc:
            logger.info("SBOM: não foi possível buscar %s: %s", caminho, exc)
            continue
        if not texto:
            continue
        for dep in parse_dependencies(texto, caminho):
            inventario.append((dep.package, dep.lower_bound, dep.file))
    return inventario


def sbom_rows(inventario: list[tuple[str, str, str]], repo: str, now: datetime) -> list[dict]:
    return [
        {
            "package": pacote,
            "declared": versao,
            "file": arquivo,
            "source_repo": repo,
            "computed_at": now,
            "policy_version": POLICY_VERSION,
        }
        for pacote, versao, arquivo in inventario
    ]


def finding_row(finding: DependencyFinding, now: datetime) -> dict:
    return {
        "sha": finding.sha,
        "package": finding.package,
        "declared": finding.declared,
        "fixed_in": finding.fixed_in,
        "severity": finding.severity,
        "cve": finding.cve,
        "file": finding.file,
        "computed_at": now,
        "policy_version": POLICY_VERSION,
    }


def inventory_findings(
    inventario: list[tuple[str, str, str]], advisories: dict[str, tuple[Advisory, ...]]
) -> list[DependencyFinding]:
    from eict.domain.supply_chain import Dependency

    findings: list[DependencyFinding] = []
    for pacote, versao, arquivo in inventario:
        for adv in match(Dependency(pacote, versao, arquivo), advisories):
            findings.append(DependencyFinding("", pacote, versao, adv.fixed_in, adv.severity, adv.cve, arquivo))
    return findings


def build_finding_rows(
    inventario: list[tuple[str, str, str]],
    changes: list,
    advisories: dict[str, tuple[Advisory, ...]],
    now: datetime,
) -> list[dict]:
    findings = inventory_findings(inventario, advisories)
    for change in changes:
        findings += scan_change(change, advisories)
    return [finding_row(f, now) for f in findings]


def main(argv: list[str] | None = None) -> None:
    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession

    settings = parse_settings(argv)
    spark = SparkSession.builder.getOrCreate()
    now = datetime.now(UTC)

    advisories = load_advisories(settings.advisories_dir)
    try:
        client = github_client(WorkspaceClient(), settings)
    except Exception as exc:
        logger.info("supply_chain: sem cliente GitHub (%s); SBOM vazio", exc)
        client = None
    inventario = build_sbom(client)
    changes = load_changes(spark, settings)

    store.replace_rows(
        spark, settings.table("ops", "dependencies"), sbom_rows(inventario, monitored_repo(settings), now)
    )
    store.replace_rows(
        spark,
        settings.table("ops", "dependency_findings"),
        build_finding_rows(inventario, changes, advisories, now),
    )
    logger.info("supply_chain: SBOM com %s dep(s); avaliação concluída", len(inventario))


if __name__ == "__main__":
    main()
