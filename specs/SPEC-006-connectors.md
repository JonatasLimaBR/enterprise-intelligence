# SPEC-006 — Framework de Conectores

## Tipos

Polling, webhook, stream, file/object ingestion e federated query.

## Interface

Cada connector implementa discovery, incremental cursor, schema mapping, health, rate-limit handling, backfill, redaction, checkpoint e deletion semantics.

## Conectores prioritários

1. Databricks: jobs, runs, system tables, billing, compute, query history, Unity Catalog lineage/audit.
2. GitHub/GitLab/Azure DevOps: repos, commits, PRs, checks, deployments e provenance.
3. Jira/ServiceNow: incidents, problems, changes, comments e SLAs.
4. OpenTelemetry: metrics, logs e traces.
5. SAST/SCA/SBOM: findings, packages, versions e CVEs.
6. Teams/Slack: war room e interação.
7. ADF/Airflow/dbt/Snowflake/SAP: fases seguintes.

## Segurança

Credenciais por connector e tenant; escopo read-only default; secret manager; rotação; allowlist de endpoints; egress control; payload size; malware scan para anexos.

## Operação

Health state, last success, lag, cursor, items/min, error rate, throttling, DLQ e replay. Connector quebrado gera incidente da própria plataforma sem recursão infinita.

