# Roadmap de Entrega

## Extensão transversal — portais e Langfuse

Foundation e MVP passam a incluir shells operacional/administrativo, central de ações, identidades, read models, health de coleta e tracing IA com Langfuse. Ordem detalhada em `../engineering/PORTALS-LANGFUSE-DELIVERY.md`; priorização das 86 telas em `../ux/SCREEN-CATALOG.md`. Implementar as rotas por ondas, sem remover os demais domínios do produto. Observabilidade antecede habilitação de remediação em produção.

## Fase 0 — Discovery e fundação (4–6 semanas)

- escolher 3–5 serviços críticos;
- inventário, owners e SLAs;
- mapear fontes e acessos;
- baseline de métricas atuais;
- arquitetura, security/privacy assessment;
- dataset de incidentes históricos;
- critérios de sucesso.

## Fase 1 — MVP DataOps Databricks (8–12 semanas)

- connectors Databricks + Git + ITSM;
- event model e stores;
- catalog/topology mínimo;
- runtime/cost/freshness baselines;
- incident lifecycle e SLA risk;
- comparação de runs e change correlation;
- console operacional e executive summary;
- audit e RBAC;
- read-only recommendations.

## Fase 2 — Quality, graph e problem (8–12 semanas)

- data contracts e quality integration;
- Unity Catalog lineage;
- blast radius;
- recurring incident clustering;
- runbooks/knowledge;
- FinOps avançado;
- Teams/Slack war room.

## Fase 3 — Code e Security (10–14 semanas)

- PR/change risk;
- SAST/SCA/SBOM/secrets/IaC;
- supply chain graph;
- provenance attestations;
- deployment gates;
- limited L2 actions.

## Fase 4 — AI/ML/RAG/Agents (10–16 semanas)

- model/agent registry;
- drift/evaluation;
- prompt/RAG telemetry;
- tool security e handoffs;
- cost and quality;
- AI governance workflows.

## Fase 5 — Enterprise Intelligence (contínua)

- semantic registry e conflitos;
- ontologia por domínio;
- process intelligence;
- financial impact calibration;
- cross-platform/cloud;
- ações L3 seletivas.

## Equipe de referência MVP

Product Owner, Tech Lead/Architect, 2 backend/data engineers, frontend, platform/SRE, security parcial, data steward/domain SME e designer parcial.

## Gates por fase

Valor medido, segurança aprovada, SLOs, qualidade de evidence, adoção, custo sustentável e readiness operacional.
