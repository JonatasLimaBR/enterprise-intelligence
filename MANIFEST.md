# Manifesto do Pacote

Este kit contém documentação de produto e engenharia, não uma implementação executável.

## Cobertura

- Contexto consolidado: `CONTEXT.md`
- Visão e índice: `README.md`, `GLOSSARY.md`
- Requisitos: 13 PRDs
- Decisões: 21 ADRs
- Contratos técnicos: 17 SPECs
- Arquitetura: visão geral e referência Databricks
- Engenharia: guia, testes e CI/CD
- Segurança: threat model, controles e LGPD/AI governance
- Governança: ontologia, operating model e risk register
- Operações: SLOs, ITSM e runbooks
- Roadmap: fases, backlog e implementation plan
- UX: information architecture, catálogo de 52 telas operacionais + 34 administrativas e contratos das telas críticas
- Dashboards: 20 visões com fontes, cadências, fórmulas e drill-down
- Langfuse: instrumentação, avaliações, isolamento, masking, correlação e saúde do exporter
- Templates: incidente, postmortem, contrato e ADR
- Rastreabilidade e aceite: `TRACEABILITY.md`, `ACCEPTANCE-CATALOG.md`

## Assunções a validar no discovery

- fornecedor ITSM e canal de colaboração;
- cloud/edição/região Databricks;
- volume de eventos e retenção;
- residência de dados;
- processos e SLAs prioritários;
- ferramentas Git/CI/security existentes;
- modelo de deployment SaaS, customer-managed ou dedicado;
- tolerância de autonomia;
- metodologia financeira e de criticidade.
