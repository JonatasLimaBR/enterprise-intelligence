# Catálogo de telas — Portais EICT

## Escopo
Inventário de telas de todo o escopo conhecido, com rotas propostas, dados e ações. Não implica entrega simultânea de todas no MVP. Rotas de detalhe incluem abas e estados. Permissionamento é sempre por recurso/tenant além do perfil da tabela.

## Contrato visual comum
Header: organização/ambiente, busca permissionada, período/fuso, freshness, notificações e identidade. Navegação distinta para /ops e /admin. Breadcrumb conserva contexto. Tabelas têm paginação, sort/filtros no servidor, seleção explícita e export autorizado. Cada painel exibe fonte, cobertura e última atualização.

Estados obrigatórios em todas as telas: carregando; sem registros; sem conexão; sem acesso; erro recuperável; dados parciais; fonte atrasada; sessão expirada. Edições acrescentam validação de campo, alteração não salva, conflito de versão, revisão pendente, sucesso e falha. Desabilitar ação com motivo; esconder botão não substitui autorização.

## Portal de operação e visualização
| ID | Tela/rota | Perfil | Dados e interação principal |
|---|---|---|---|
| OPS-01 | /ops/overview — Executivo | Gestor/Viewer | Saúde, impacto, riscos e SLA; drill-down por domínio. |
| OPS-02 | /ops/my-work — Minha fila | Operador | Incidentes atribuídos, aprovações, ações vencidas; ordenar por prioridade. |
| OPS-03 | /ops/activities — Todas as ações | Operador/Auditor | Evento, ator, origem, alvo e resultado; busca por correlação. |
| OPS-04 | /ops/actions/:id — Ação | Operador/Aprovador | Plano, decisão, execução, evidência e sync; cancelar via workflow. |
| OPS-05 | /ops/approvals — Aprovações | Aprovador | Pendentes, expiração, risco e owner; sem aprovação em massa no MVP. |
| OPS-06 | /ops/approvals/:id — Revisão | Aprovador | Diff imutável, parâmetros, custo e contingência; aprovar/rejeitar autenticado. |
| OPS-07 | /ops/executions — Execuções | Operador | Estado, heartbeat, worker, duração e bloqueio. |
| OPS-08 | /ops/executions/:id — Detalhe | Operador | Steps, logs redigidos, effect status, verificação; sem retry cego. |
| OPS-09 | /ops/recovery — Recuperação | SRE/Owner | Antes/depois, checks, janela, inconclusivos; solicitar fechamento. |
| OPS-10 | /ops/incidents — Incidentes | Operador | P1–P4, owner, SLA, impacto e correlatos. |
| OPS-11 | /ops/incidents/:id — Workspace | Operador | Timeline, RCA, changes, impacto, ações e ITSM. |
| OPS-12 | /ops/war-rooms/:id — War room | Equipe autorizada | Updates, participantes, decisões e próximo checkpoint. |
| OPS-13 | /ops/problems — Problemas | Sustentação | Recorrência, causa, known errors e ação permanente. |
| OPS-14 | /ops/changes — Mudanças | Engenharia | PR/deploy, risco, gates, incidente correlacionado. |
| OPS-15 | /ops/risks — Riscos | Gestor/Owner | Probabilidade/impacto, evidências, mitigação e aceites. |
| OPS-16 | /ops/slos — SLA/SLO | Owner | ETA, burn rate, violações, calendário e confiança. |
| OPS-17 | /ops/assets — Inventário | Viewer | Tipo, criticidade, domínio e owner; lacunas. |
| OPS-18 | /ops/assets/:id — Ativo | Viewer | Dependências, saúde, mudanças, custo e classificação. |
| OPS-19 | /ops/graph — Grafo/lineage | Engenharia/Steward | Caminhos, direção, temporalidade e confiança; expansão limitada. |
| OPS-20 | /ops/pipelines — Pipelines | Dados | DAG, estado e critical path. |
| OPS-21 | /ops/runs/:id — Run | Dados | Tasks, retries, volume, parâmetros e evidências. |
| OPS-22 | /ops/spark — Spark | Dados | Stage/task, skew, spill, memória, GC e comparação saudável. |
| OPS-23 | /ops/queries — Queries | Dados | Regressões, plano, scan, pruning, fila e custo. |
| OPS-24 | /ops/quality — Qualidade | Steward | Dimensões, regras, severidade e freshness. |
| OPS-25 | /ops/contracts/:id — Contrato | Steward/Owner | Schema, compatibilidade, consumidores e violações. |
| OPS-26 | /ops/semantics — Métricas de negócio | Business/Steward | Definição, versão, conflito e consumidores. |
| OPS-27 | /ops/ai — Saúde IA | AI Owner | Sucesso, erro, latência, avaliação e custo. |
| OPS-28 | /ops/agents/:id — Agente | IA | Versão, tools, limites, incidentes e dependências. |
| OPS-29 | /ops/traces — Explorer | IA/Operador | Trace, sessão, release, duração, erro e custo. |
| OPS-30 | /ops/traces/:id — Trace | IA com escopo | Waterfall, retrieval, gerações e tools; payload redigido. |
| OPS-31 | /ops/sessions/:id — Sessão | IA com escopo | Turnos, traces ligados e feedback; identidade pseudônima. |
| OPS-32 | /ops/handoffs — Handoffs | IA | Origem/destino, timeout, dados faltantes e retorno. |
| OPS-33 | /ops/tools — Tools/MCP | IA/Security | Invocações, denials, privilégios e efeito. |
| OPS-34 | /ops/prompts — Prompts | IA | Versões, release, regressões e qualidade; editar via workflow. |
| OPS-35 | /ops/evaluations — Avaliações | IA | Rubricas, amostra, scores, falhas e avaliador. |
| OPS-36 | /ops/experiments/:id — Experimento | IA | Dataset/variantes, qualidade, custo e decisão de promoção. |
| OPS-37 | /ops/rag — RAG | IA/Dados | Atualidade, retrieval, documentos/chunks e cobertura. |
| OPS-38 | /ops/models — Modelos | ML/AI | Versão, drift, features, serving e disponibilidade. |
| OPS-39 | /ops/tokens — Tokens | FinOps/IA | Input/output/cache, loops, budget e custo/sucesso. |
| OPS-40 | /ops/gateway — Unity Gateway | IA/Security | Policies, routing, fallback, quotas e capability gaps. |
| OPS-41 | /ops/code — Código | Engenharia | Complexidade, testes, findings, proveniência e PRs. |
| OPS-42 | /ops/security — Segurança | Security | Vulnerabilidades, exposição, dados e agentes afetados. |
| OPS-43 | /ops/supply-chain — Supply chain | Security | SBOM, pacote, artefato, deploy e impacto de CVE. |
| OPS-44 | /ops/finops — FinOps | FinOps/Gestor | Gasto, alocação, forecast, orçamento e reconciliação. |
| OPS-45 | /ops/improvements — Melhorias | Owner | Oportunidades, investimento, experimento e savings realizadas. |
| OPS-46 | /ops/processes/:id — Processo | Business Owner | Etapas, gargalos, SLA, sistemas e impacto. |
| OPS-47 | /ops/knowledge — Conhecimento | Sustentação | Runbooks, problemas similares, eficácia e validade. |
| OPS-48 | /ops/postmortems/:id — Postmortem | Sustentação | Timeline factual, causas confirmadas, revisão e ações. |
| OPS-49 | /ops/communications — Comunicação | Operador | Entrega Teams/WhatsApp, sync ITSM, falhas e retries. |
| OPS-50 | /ops/reports — Relatórios | Gestor/Auditor | Exports permissionados, snapshots e vencimento. |
| OPS-51 | /ops/audit — Auditoria | Auditor | Atores, decisões, hashes e efeitos; export auditado. |
| OPS-52 | /ops/platform — Saúde da plataforma | Platform/SRE | APIs, queues, connector lag, DLQ e exporter. |

## Portal administrativo
| ID | Tela/rota | Perfil | Campos e operação principal |
|---|---|---|---|
| ADM-01 | /admin/overview | PlatformAdmin | Configurações pendentes, riscos, drift e integrações. |
| ADM-02 | /admin/organization | OrgAdmin | Unidades, domínios, owners e criticidade. |
| ADM-03 | /admin/users | IdentityAdmin | Usuários, grupos, status e escopos. |
| ADM-04 | /admin/roles | SecurityAdmin | Permissões, SoD, revisão e preview de acesso efetivo. |
| ADM-05 | /admin/auth | IdentityAdmin | SSO/session/MFA, teste e validação sem expor secrets. |
| ADM-06 | /admin/workloads | PlatformAdmin | Service principals, scopes, expiração e referência de credencial. |
| ADM-07 | /admin/connectors | IntegrationAdmin | Catálogo de adapters, health, lag e capabilities. |
| ADM-08 | /admin/connectors/:id | IntegrationAdmin | Endpoint, secret ref, cursor, coleta, redaction e teste read-only. |
| ADM-09 | /admin/itsm | IntegrationAdmin | Campos, prioridade, estados, precedência e sync. |
| ADM-10 | /admin/channels | IntegrationAdmin | Teams/WhatsApp, identidades, templates e delivery policy. |
| ADM-11 | /admin/oncall | OpsAdmin | Grupos, escala, timezone, substituição e escalonamento. |
| ADM-12 | /admin/slos | DomainAdmin | Calendário, SLIs, limites, janela e burn-rate rules. |
| ADM-13 | /admin/detection | DomainAdmin | Regras, thresholds, suppression e simulação. |
| ADM-14 | /admin/correlation | DomainAdmin | Fingerprints, janelas, causalidade candidata e replay de fixture. |
| ADM-15 | /admin/policies | SecurityAdmin | Autorizações, versões, impacto, revisão e publicação. |
| ADM-16 | /admin/approvals | Security/OpsAdmin | Aprovadores, quórum, expiração, SoD e fechamento P1. |
| ADM-17 | /admin/runbooks | OpsAdmin | Allowlist, digest, parâmetros, contingência e histórico. |
| ADM-18 | /admin/execution | PlatformAdmin | Workers, quotas, leases, permissões e kill switch. |
| ADM-19 | /admin/agents | AIAdmin | Agentes, modelos, tools permitidas, orçamento e autonomia. |
| ADM-20 | /admin/tools | AI/SecurityAdmin | MCP/tools, schemas, risco, scopes e network allowlist. |
| ADM-21 | /admin/langfuse | AI/PlatformAdmin | Deployment, projeto, secret ref, mapping e compatibility. |
| ADM-22 | /admin/telemetry | PlatformAdmin | Sampling, masking, filas, retention e exporter health. |
| ADM-23 | /admin/evaluators | AIAdmin | Rubricas, judges, calibração, dataset e promotion gates. |
| ADM-24 | /admin/gateway | AI/SecurityAdmin | Estado desejado/observado, budgets, routing e policies. |
| ADM-25 | /admin/finops | FinOpsAdmin | Cost centers, allocation, pricing refs, budgets e moedas. |
| ADM-26 | /admin/contracts | DataAdmin | Regras, schemas, owners e compatibilidade. |
| ADM-27 | /admin/ontology | DataAdmin | Tipos, relações, temporalidade e revisão. |
| ADM-28 | /admin/semantics | Data/BusinessAdmin | Métricas canônicas, fórmula, grão e aprovação. |
| ADM-29 | /admin/privacy | PrivacyAdmin | Classes, retention, redaction, deletion e legal hold. |
| ADM-30 | /admin/dashboards | DomainAdmin | Widgets allowlisted, filtros, pesos e compartilhamento. |
| ADM-31 | /admin/maintenance | OpsAdmin | Freeze/janelas, timezone e serviços afetados. |
| ADM-32 | /admin/features | PlatformAdmin | Rollout por domínio, read-only e critérios de promoção. |
| ADM-33 | /admin/queues | PlatformAdmin | DLQ, erros, replay delimitado e backpressure. |
| ADM-34 | /admin/audit | Auditor/Security | Histórico de configuração, revisões e exceções vencidas. |

## Telas compartilhadas
Login/SSO; sessão expirada; selecionar organização autorizada; acesso negado; recurso inexistente; centro de notificações; perfil/fuso/idioma; preferências de acessibilidade; manutenção; ajuda e glossário. Não contam como rotas de domínio acima.

## Contrato de detalhe e edição
Cada tela-lista abre detalhe por ID com abas Overview, Histórico e Evidências conforme entidade. Toda edição administrativa apresenta campos tipados, owner, motivo, diff e revisão. Exclusão é preferencialmente desativação/depreciação com dependências visíveis; conteúdo com obrigação de retenção exige fluxo próprio. A busca não sugere identificadores de tenants proibidos.

## Priorização
MVP: OPS-01–12, OPS-16–18, OPS-20–24, OPS-29–30, OPS-39, OPS-49, OPS-52; ADM-01–10, ADM-12, ADM-15–18, ADM-21–22, ADM-29 e ADM-34. Remediação começa sandbox/read-only e depois L2 aprovado.
Onda 2: qualidade/contratos/grafo, avaliações, FinOps completo e melhorias.
Onda 3: semântica/ontologia, processos e integrações avançadas. Links para funcionalidades ainda não habilitadas mostram estado planejado e não uma tela vazia com dados inventados.

