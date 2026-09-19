# PRD-000 — Produto Mestre

## 1. Identificação

- Produto: Enterprise Intelligence Control Tower (EICT)
- Categoria: Enterprise Operations, Data/AI/Engineering Intelligence
- Status: proposta detalhada
- Público: empresas médias e grandes com ecossistemas híbridos/multicloud
- Modelo: plataforma modular, API-first, event-driven e extensível

## 2. Problema

As organizações possuem telemetria fragmentada. Operações veem alertas, engenharia vê logs, dados veem pipelines, segurança vê findings e o negócio vê efeitos tardios. A investigação é manual, os tickets não carregam contexto suficiente, mudanças não são correlacionadas, incidentes se repetem e decisões são priorizadas por ruído técnico em vez de impacto.

## 3. Visão

Criar um mapa vivo da organização e uma camada de inteligência capaz de transformar observações dispersas em incidentes, riscos, causas prováveis, impacto, responsabilidades e ações governadas.

## 4. Objetivos

- Reduzir MTTD, MTTA e MTTR.
- Prever violações de SLA antes que ocorram.
- Reduzir incidentes recorrentes e change failure rate.
- Associar sinais técnicos a impacto de negócio.
- Aumentar confiabilidade, qualidade e segurança de dados, IA e software.
- Reduzir custo computacional e desperdício.
- Governar código assistido por IA com evidência e políticas proporcionais.
- Produzir conhecimento reutilizável a cada resolução.

## 5. Não objetivos iniciais

- Substituir ITSM, SIEM, observability, catálogo, Git ou CI/CD.
- Ser uma IDE, scanner SAST ou data quality engine completo.
- Executar remediação irrestrita.
- Classificar autoria de código por IA como fato sem provenance.
- Centralizar todos os dados brutos quando integração federada for suficiente.

## 6. Personas

| Persona | Necessidade principal |
|---|---|
| Operador N1/N2 | Saber prioridade, contexto, owner e runbook. |
| Data Engineer | Encontrar causa em pipelines/Spark e validar correção. |
| SRE/Platform Engineer | Entender dependências, capacidade e mudanças. |
| Security Engineer | Priorizar findings por exposição e blast radius. |
| ML/AI Engineer | Monitorar modelos, RAG e agentes. |
| Data Steward/CDO | Governar qualidade, lineage, contratos e semântica. |
| Engineering Manager | Avaliar risco de mudança e saúde de entrega. |
| Product/Process Owner | Entender impacto em processo e cliente. |
| CTO/CIO/CISO | Priorizar risco, investimento e transformação. |
| Auditor/DPO | Ver evidências, acesso, retenção e conformidade. |

## 7. Jobs to be done

- Quando um serviço degrada, quero entender causa e impacto sem navegar por dez ferramentas.
- Antes de uma mudança, quero saber seu risco e quais aprovações exigir.
- Quando um pipeline termina verde, quero confirmar que os dados estão corretos.
- Quando surge uma CVE, quero saber exatamente quais aplicações e processos estão expostos.
- Quando um agente falha, quero distinguir problema de prompt, retrieval, tool ou dado.
- Quando um KPI diverge, quero localizar definições conflitantes.
- Quando incidentes se repetem, quero transformá-los em problema e prevenção.

## 8. Capacidades funcionais

### CF-01 Ingestão e normalização

Conectores recebem métricas, logs, traces, eventos, metadata, lineage, findings, changes, tickets e fatos de negócio. Eventos devem ter tenant, fonte, tempo do evento, tempo de ingestão, identidade, asset e classificação.

### CF-02 Inventário e topologia

Catálogo unificado de sistemas, aplicações, serviços, datasets, pipelines, modelos, agentes, repositórios, artefatos, dependências, owners e processos.

### CF-03 Correlação e detecção

Deduplicação, agrupamento temporal/topológico, baseline, anomalias, regras, correlação com changes e formação de incidentes.

### CF-04 RCA assistido

Hipóteses ranqueadas, evidências pró/contra, confiança, diferenças em relação à última condição saudável, runbooks e incidentes semelhantes.

### CF-05 Impacto

Blast radius técnico e empresarial; clientes, receita, SLA, processos, compliance e dados sensíveis afetados.

### CF-06 Gestão operacional

Incidentes, problemas, mudanças, timeline, ownership, colaboração, escalonamento, war room, postmortem e knowledge base.

### CF-07 Data Intelligence

Spark, pipelines, SQL, quality, contracts, lineage, semantic layer, custo e capacidade.

### CF-08 AI Intelligence

Modelos, features, GenAI, RAG, agentes, avaliações, drift, custo, segurança e autonomia.

### CF-09 Code Intelligence

Qualidade, testes, security findings, dependências, performance, provenance e Change Risk Score.

### CF-10 Security Intelligence

Identity, posture, SAST/SCA, containers, IaC, supply chain, PII, runtime e agent security.

### CF-11 Recommendations and Actions

Recomendação explicável, simulação, aprovação, execução idempotente, validação e rollback.

### CF-12 Executive Intelligence

Enterprise Health, top risks, tendência, custo do risco, impacto evitado e recomendações estratégicas.

## 9. Requisitos não funcionais

- Multi-tenant lógico e isolamento forte.
- Disponibilidade alvo: 99,9% no core; componentes críticos configuráveis para 99,95%.
- Ingestão p95 inferior a 60 segundos para eventos operacionais críticos.
- Consulta de incidente p95 inferior a 2 segundos sem enriquecimento LLM.
- Auditoria append-only de decisões e ações.
- Criptografia em trânsito e repouso.
- RBAC + ABAC e segregação por domínio, ambiente e sensibilidade.
- Degradação segura quando LLM ou integração externa falhar.
- Portabilidade de dados e conectores.
- Retenção configurável por classe de dado.

## 10. Métricas de produto

### North Star

**Percentual de incidentes relevantes resolvidos dentro do SLO com diagnóstico e impacto validados.**

### Métricas complementares

- redução de MTTR e MTTD;
- precisão de deduplicação;
- top-3 RCA hit rate validado por humanos;
- predicted breach precision/recall;
- taxa de recomendações aceitas;
- automações bem-sucedidas sem rollback;
- redução de recorrência em 30/90 dias;
- economia comprovada de compute;
- cobertura do grafo e assets com owner;
- falsos positivos de policy gates;
- satisfação dos operadores.

## 11. Escopo MVP

- Um workspace/account Databricks e um repositório Git.
- Lakeflow Jobs, system tables, Unity Catalog lineage, billing e cluster metrics.
- Ingestão de eventos, catálogo mínimo e grafo de dependências.
- Baseline de runtime/custo/freshness e detecção de anomalia.
- Incidente, SLA previsto, RCA inicial e change correlation.
- Integração Jira ou ServiceNow em um sentido, depois bidirecional.
- Dashboard operacional, tela de incidente e resumo executivo.
- Read-only; recomendações sem remediação automática.

## 12. Critérios de saída do MVP

- Detectar pelo menos 80% dos cenários sintéticos acordados.
- Menos de 10% de duplicação indevida de incidentes.
- Explicar 100% dos scores com evidências acessíveis.
- Correlacionar commit/deploy em pelo menos 70% das regressões injetadas.
- Criar/sincronizar ticket com idempotência.
- Não expor secrets ou payload sensível em logs.
- Auditoria completa das interações e decisões do agente.

## 13. Dependências

Patrocínio executivo, owners dos domínios, acesso read-only às fontes, catálogo mínimo, identidade corporativa, dados de custo, definição de SLAs e processo ITSM.

## 14. Riscos

- baixa qualidade de metadata;
- excesso de alertas e confiança reduzida;
- custo de ingestão e retenção;
- resistência organizacional;
- uso indevido de scores de autoria de código;
- remediação prematura;
- dependência excessiva de LLM;
- cobertura incompleta do grafo.

## 15. Guardrails de produto

- Mostrar lacunas de evidência.
- Separar fato, inferência e recomendação.
- Exigir justificativa e trilha para overrides.
- Não penalizar indivíduos por AI-likeness.
- Executar ação somente dentro de política declarada.
- Permitir contestação e correção de ownership/semântica.

