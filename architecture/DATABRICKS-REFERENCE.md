# Implementação de Referência Databricks

## Objetivo

Entregar o primeiro vertical de valor usando sinais de jobs, compute, queries, catálogo, lineage, audit e billing, sem acoplar o domínio central ao fornecedor.

## Fontes e usos

| Fonte | Uso |
|---|---|
| Jobs/Lakeflow metadata | runs, tarefas, dependências, retries e duração. |
| Compute/system metrics | CPU, memória, disco, rede, configuração e capacidade. |
| Query history | regressões SQL, filas, leitura e duração. |
| Billing usage | custo por workload/tag/owner. |
| Unity Catalog | assets, ownership, privilégios, lineage e audit. |
| Spark event logs/metrics | stage/task, skew, spill, GC e executor. |
| Git/CI metadata | commits, PRs, deploys e provenance. |
| Unity Gateway | modelos, agentes, MCP/tools, access policies, tokens, budgets, routing e guardrails. |
| Inference tables | requests/responses governados para debugging, avaliação e auditoria quando aprovados. |

## Modelo medallion sugerido

- Bronze: snapshots/eventos crus com retenção e hash.
- Silver: entidades canônicas de job, run, query, compute, cost, asset e change.
- Gold: baselines, anomalies, health, cost attribution, SLA risk e incident features.

## Casos iniciais

1. runtime regression;
2. data skew e spill;
3. upstream missing/freshness;
4. SQL regression;
5. compute saturation/mis-sizing;
6. cost anomaly;
7. failed/retried tasks;
8. change-correlated degradation;
9. lineage impact;
10. contract/data quality violation.
11. token/cost anomaly, loop, fallback e budget/rate-limit;
12. policy violation em modelo, agente, MCP server ou tool.

## Limites

Disponibilidade e schema das system tables variam por cloud, região e edição. Cada capability deve ser detectada dinamicamente; o produto exibe `not_available`, não dado inventado. Free Edition serve para protótipo/demonstração e não representa arquitetura de produção empresarial. Recursos do Unity Gateway também variam por região, workspace e disponibilidade; o adapter deve descobrir capacidades.

## Segurança

Service principal read-only, permissions mínimas, catálogo dedicado, masking e não ingestão de resultados SQL sensíveis por padrão.
