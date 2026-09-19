# ADR-018 — Integrar Unity Gateway como enforcement, não duplicá-lo

- Status: Aceita

## Contexto

Databricks Unity Gateway oferece governance de serviços de IA, modelos, agentes, MCP e tools com Unity Catalog, além de access control, service policies, traffic management, budgets e observabilidade.

## Decisão

Usar Unity Gateway como plano de enforcement no vertical Databricks. A EICT ingere e correlaciona seus sinais com incidentes, mudanças, processos e FinOps, mantendo modelo canônico para outros gateways/providers. Não duplicar controle já aplicado; não depender do LLM para autorização.

Inference tables são opcionais e governadas. A plataforma prefere metadata/métricas; payload completo permanece no domínio Databricks quando possível e é acessado por referência sob autorização.

## Consequências

Governança nativa e menor duplicação, com dependência de capabilities por região/workspace e custos adicionais de recursos como inference tables. Capability discovery e fallback agnóstico são obrigatórios.

