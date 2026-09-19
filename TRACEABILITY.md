# Matriz de Rastreabilidade

| Capacidade | PRD | ADR principal | SPEC | Teste/Operação |
|---|---|---|---|---|
| Eventos canônicos | PRD-000 | ADR-001 | SPEC-002 | TEST-STRATEGY |
| Persistência | PRD-000 | ADR-002 | SPEC-001 | SLO-OBSERVABILITY |
| Ontologia/grafo | PRD-020 | ADR-003 | SPEC-001 | ONTOLOGY-SEMANTIC-MODEL |
| Multiagentes | PRD-030/060 | ADR-004 | SPEC-007 | TEST-STRATEGY |
| RCA | PRD-010 | ADR-005 | SPEC-004 | RUNBOOKS |
| Proveniência código | PRD-040 | ADR-006 | SPEC-009 | LGPD-AI-GOVERNANCE |
| Policy/action | PRD-060 | ADR-007/008 | SPEC-007/009 | SECURITY-CONTROLS |
| Zero Trust | PRD-040 | ADR-009 | SPEC-003/006 | THREAT-MODEL |
| Databricks MVP | PRD-010 | ADR-010 | SPEC-006 | DATABRICKS-REFERENCE |
| Scores | PRD-050 | ADR-011 | SPEC-005 | GOVERNANCE-OPERATING-MODEL |
| Privacidade | todos | ADR-012 | SPEC-001/007 | LGPD-AI-GOVERNANCE |
| Integrações | PRD-000 | ADR-013/015 | SPEC-003/006 | CI-CD |
| SLO | PRD-010 | ADR-014 | SPEC-004 | SLO-OBSERVABILITY |
| Multi-tenant | PRD-000 | ADR-016 | SPEC-001/003 | THREAT-MODEL |
| Chamado automático e gestor via Teams/WhatsApp | PRD-010/060 | ADR-007/013 | SPEC-010/011 | ACCEPTANCE-CATALOG |
| FinOps e melhoria contínua | PRD-070 | ADR-017 | SPEC-012 | CONTINUOUS-IMPROVEMENT |
| Tokens e Databricks Unity Gateway | PRD-080 | ADR-018 | SPEC-013 | DATABRICKS-REFERENCE |

## Regra de manutenção

| Extensão | Produto | Decisão | Especificação | Interface/testes |
|---|---|---|---|---|
| Portal operacional e ações | PRD-100 | ADR-020 | SPEC-015/017 | SCREEN-CATALOG / PORTALS-LANGFUSE-DELIVERY |
| Portal administrativo | PRD-110 | ADR-020 | SPEC-015 | CRITICAL-SCREEN-CONTRACTS |
| Langfuse e tracing | PRD-120 | ADR-021 | SPEC-016 | PORTALS-OBSERVABILITY / PORTALS-LANGFUSE-DELIVERY |

Remediação aprovada: PRD-090 → ADR-019 → SPEC-014. Integra-se a PRD-010/060 e SPEC-011, com testes de aprovação, concorrência, efeitos incertos, rollback e fechamento validado.

Todo requisito novo deve apontar para: owner, critério de aceite, decisão arquitetural afetada, contrato técnico e estratégia de teste. Requisitos sem método de verificação não entram como “prontos”.
