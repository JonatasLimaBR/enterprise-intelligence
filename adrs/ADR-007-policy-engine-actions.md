# ADR-007 — Policy engine externo ao LLM

- Status: Aceita

## Decisão

Autorização, gates, segregation of duties e limites de ação são avaliados por motor determinístico e versionado. O LLM não concede privilégios nem altera policy em runtime.

Inputs: principal, tenant, action, resource, environment, risk, classification, approval e context claims. Output: allow/deny/require-approval com policy ID e versão.

## Consequências

Decisões reproduzíveis e auditáveis; aumenta esforço de modelagem de políticas.

