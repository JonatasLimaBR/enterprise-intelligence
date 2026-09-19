# EICT Platform

Plataforma da demo: coleta sinais do workspace, correlaciona em incidentes com evidência e expõe o console.

## Estrutura

```text
databricks.yml            bundle (variáveis, target dev)
resources/                schemas, volume, job eict_cycle, pipeline Lakeflow, app
src/eict/domain/          núcleo puro (sem Databricks) — baseline, diff, hipóteses, incidentes, custo, narrativa
src/eict/adapters/        Jobs API, GitHub, Jira, LLM, Delta store, capability discovery
src/eict/jobs/            entry points das 5 tasks do ciclo
pipelines/medallion.py    silver.runs / changes / run_profiles → silver.run_features
app/                      console Streamlit (Databricks App)
tests/                    unit (sem Spark) + spark (marcador `spark`)
```

## Pré-requisitos

1. Profile do CLI autenticado (`databricks auth login --host <url> --profile eict`).
2. Secret scope com os tokens:

```bash
databricks secrets create-scope eict --profile eict
databricks secrets put-secret eict github_token --profile eict
databricks secrets put-secret eict jira_email --profile eict
databricks secrets put-secret eict jira_token --profile eict
```

3. Variáveis do bundle: `github_repo`, `jira_base_url`, `jira_project`, `warehouse_id`, `llm_endpoint`.

## Deploy

```bash
export VARS='--var=warehouse_id=<id>,github_repo=<owner/repo>,jira_base_url=<https://site.atlassian.net>,jira_project=<KEY>'
databricks bundle validate -t dev --profile <seu-profile> $VARS
databricks bundle deploy   -t dev --profile <seu-profile> $VARS
databricks bundle run eict_cycle -t dev --profile <seu-profile> $VARS
```

`warehouse_id` não tem valor padrão: pegue o seu com `databricks warehouses list --profile <seu-profile>`.

O `eict_cycle` roda a cada 5 minutos: `bootstrap → collect → medallion → correlate → narrate → dispatch`.
Para a apresentação, dispare manualmente com `bundle run` logo após o run lento do workload.

## Desenvolvimento

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -q                       # unit, sem Spark
.venv/Scripts/python -m pytest -m spark                 # exige Java + pyspark local
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest --cov=eict.domain --cov-fail-under=80
```

## Garantias implementadas

| Regra | Onde |
|-------|------|
| Domínio sem dependência de Databricks | `tests/unit/test_domain_purity.py` |
| Um incidente por job/tipo ativo | `domain/incidents.py::open_or_update` |
| Hipótese nunca vira causa confirmada sem humano | `domain/hypotheses.py` (cap 0.9) + review na App |
| Narrativa só cita evidence IDs existentes | `domain/narrative.py::narrate` → fallback determinístico |
| Fonte ausente vira `not_available` | `adapters/capabilities.py`, `domain/diff.py` |
| Ticket Jira idempotente | `adapters/jira.py::ensure_issue` + outbox em `jobs/dispatch.py` |

## Limites conhecidos no workspace atual

- `system.billing.*` exige account admin: custo aparece como `not_available` até o grant.
- Workspace só serverless: spill/GC/partição real não existem; a evidência de skew vem do run profile do workload.
