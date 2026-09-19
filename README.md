# Enterprise Engineering & Operations Intelligence

Kit completo de definição de produto e engenharia para uma Control Tower cognitiva capaz de correlacionar operação, dados, aplicações, código, segurança, IA, processos, custos e impacto de negócio.

## Proposta em uma frase

Uma camada de inteligência acima das ferramentas corporativas que responde: **o que aconteceu, por que aconteceu, qual o impacto, quem deve agir, o que fazer agora e como evitar recorrência**.

## Pilares

1. DataOps e observabilidade de pipelines.
2. Spark/Databricks Intelligence.
3. Qualidade, contratos, catálogo e lineage de dados.
4. MLOps, LLMOps, RAG e agentes.
5. Camada semântica, ontologia e knowledge graph.
6. Process e Business Impact Intelligence.
7. Code Intelligence e qualidade de software.
8. Security, privacy, supply chain e AI governance.
9. Incident, Problem, Change e Knowledge Management.
10. FinOps, capacidade e sustentabilidade.
11. Melhoria contínua, savings realizadas e prevenção de recorrência.

## Estrutura do kit

- `CONTEXT.md`: contexto longo consolidado desta concepção.
- `prd/`: requisitos de produto, personas, jornadas, capacidades e critérios de sucesso.
- `adrs/`: decisões arquiteturais e seus trade-offs.
- `specs/`: contratos funcionais e técnicos implementáveis.
- `architecture/`: visão C4, integrações, fluxos e modelo lógico.
- `engineering/`: padrões de desenvolvimento, testes e entrega.
- `security/`: threat model, controles, LGPD e governança de IA.
- `governance/`: ontologia, semântica, scoring e políticas.
- `operations/`: SLOs, incidentes, runbooks e operação da própria plataforma.
- `roadmap/`: MVP, fases, backlog e estratégia de adoção.
- `ux/`: mapa de telas, jornadas e requisitos de experiência.
- `templates/`: modelos operacionais reutilizáveis.

## Ordem recomendada de leitura

1. `CONTEXT.md`
2. `prd/PRD-000-master-product.md`
3. `architecture/ARCHITECTURE.md`
4. `roadmap/ROADMAP.md`
5. PRDs do domínio de interesse
6. ADRs e SPECs correspondentes

## Princípios não negociáveis

- Evidência antes de inferência.
- IA recomenda; políticas determinísticas autorizam ou bloqueiam.
- Atribuição humano/IA somente com proveniência verificável; inferência é sempre rotulada como não conclusiva.
- Segurança, privacidade, auditoria e segregação desde o desenho.
- A plataforma complementa ServiceNow, Jira, Databricks, observability e SIEM; não tenta substituí-los.
- Todo diagnóstico deve ligar evidência técnica a impacto operacional e de negócio.
- Automação de ação começa read-only e evolui por níveis de autonomia.

## Atualização — remediação aprovada

Fluxo detalhado em `prd/PRD-090-approved-remediation.md`, `specs/SPEC-014-approved-remediation-workflow.md` e `adrs/ADR-019-approval-bound-remediation.md`. Inclui aprovação autenticada, execução restrita, rollback, verificação independente e fechamento/notificação via ITSM. São especificações, não funcionalidades já implantadas.

## Portais, dashboards e Langfuse

Os PRDs 100/110/120 e SPECs 015/016/017 detalham os portais de operação e administração, monitoramento de todas as ações e observabilidade de IA com Langfuse. Consulte `ux/SCREEN-CATALOG.md` (86 telas de domínio), `ux/CRITICAL-SCREEN-CONTRACTS.md`, `architecture/PORTALS-OBSERVABILITY.md` e `engineering/PORTALS-LANGFUSE-DELIVERY.md`. O pacote é documentação para construção; não contém um portal implantado.

## Identidade do produto

**Enterprise Intelligence Control Tower (EICT)**. O nome pode ser substituído sem alterar os documentos.
