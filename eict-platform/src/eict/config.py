from __future__ import annotations

import argparse
from dataclasses import dataclass

DEFAULT_CATALOG = "workspace"
DEFAULT_SCHEMA_PREFIX = "eict_"
DEFAULT_TENANT = "demo"


@dataclass(frozen=True)
class Settings:
    catalog: str = DEFAULT_CATALOG
    schema_prefix: str = DEFAULT_SCHEMA_PREFIX
    tenant_id: str = DEFAULT_TENANT
    landing_dir: str = "/Volumes/workspace/eict_platform/landing"
    secret_scope: str = "eict"
    github_repo: str = ""
    jira_base_url: str = ""
    jira_project: str = ""
    llm_endpoint: str = ""
    contracts_dir: str = ""

    def table(self, layer: str, name: str) -> str:
        return f"{self.catalog}.{self.schema_prefix}{layer}.{name}"

    def schema(self, layer: str) -> str:
        return f"{self.catalog}.{self.schema_prefix}{layer}"

    @property
    def run_profiles_dir(self) -> str:
        return f"{self.landing_dir}/run_profiles"


def parse_settings(argv: list[str] | None = None) -> Settings:
    parser = argparse.ArgumentParser(description="EICT platform job settings")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--schema-prefix", default=DEFAULT_SCHEMA_PREFIX)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT)
    parser.add_argument("--landing-dir", default="/Volumes/workspace/eict_platform/landing")
    parser.add_argument("--secret-scope", default="eict")
    parser.add_argument("--github-repo", default="")
    parser.add_argument("--jira-base-url", default="")
    parser.add_argument("--jira-project", default="")
    parser.add_argument("--llm-endpoint", default="")
    parser.add_argument("--contracts-dir", default="")
    known, _ = parser.parse_known_args(argv)
    return Settings(
        catalog=known.catalog,
        schema_prefix=known.schema_prefix,
        tenant_id=known.tenant_id,
        landing_dir=known.landing_dir,
        secret_scope=known.secret_scope,
        github_repo=known.github_repo,
        jira_base_url=known.jira_base_url,
        jira_project=known.jira_project,
        llm_endpoint=known.llm_endpoint,
        contracts_dir=known.contracts_dir,
    )
