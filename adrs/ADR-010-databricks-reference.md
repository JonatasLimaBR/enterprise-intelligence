# ADR-010 — Databricks como implementação inicial, core agnóstico

- Status: Aceita

## Decisão

O primeiro vertical usa Databricks/Lakeflow/Unity Catalog/system tables/billing por fornecer sinais integráveis de jobs, compute, queries, lineage e custo. O domínio canônico não expõe tipos Databricks diretamente; adapters fazem a tradução.

## Consequências

Entrega valor mais rápido para DataOps sem bloquear Snowflake, Azure, AWS ou GCP. Alguns sinais terão capacidades diferentes por provider.

