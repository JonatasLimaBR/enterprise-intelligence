# SPEC-015 — Portais, backend e eventos de ações

## Arquitetura
Dois shells /ops e /admin. Backend-for-frontend (BFF) autentica e entrega dados já autorizados. APIs de domínio mantêm regras; UI não altera status diretamente. Read models/materialized views aceleram dashboards. Bus/outbox atualiza projeções e emite notificações para SSE. Permissões são reavaliadas ao conectar e durante a sessão.

## Registro universal de atividade
ActivityRecord: activity_id, tenant_id, domain_id, environment, kind, actor_type (human/agent/service), actor_id, incident_id?, plan_id?, approval_id?, execution_id?, trace_id?, parent_activity_id?, resource_refs, event_time, ingested_at, sequence, schema_version, source, status, risk, outcome, evidence_refs, classification.
Tipos: detect, correlate, classify, ticket_sync, investigate, recommend, approval_request/decision/revoke, policy_check, tool_call, execute, verify, rollback, notify, close, admin_change, export.
Não duplicar contagem da mesma execução por ter múltiplos registros. ActivityRecord descreve fatos/eventos; estado atual é projeção do workflow.

## APIs propostas do BFF
| Método/rota | Contrato |
|---|---|
| GET /v1/portal/context | Identidade, escopos permitidos, capabilities, fuso, navegação. |
| GET /v1/activities | Cursor, sort, filtros allowlisted; sem payload bruto. |
| GET /v1/activities/{id} | Evento, relações e campos permissionados. |
| GET /v1/action-dashboard | Métricas definidas em SPEC-017, janela e freshness. |
| GET /v1/dashboards/{id} | Layout versionado e widgets autorizados. |
| POST /v1/saved-views | Filtros validados e scope pessoal/equipe. |
| POST /v1/exports | Job assíncrono com escopo/filtros congelados e revalidação no download. |
| GET /v1/streams/activities | SSE com cursor e heartbeat. |
| GET /v1/admin/configurations/{id} | Versão, histórico redigido e impacto. |
| POST /v1/admin/configurations/{id}/validate | Validar schema e simular. |
| POST /v1/admin/configurations/{id}/publish | Exige revisão aplicável, If-Match e audit. |
| GET /v1/admin/telemetry-health | Backlog, drops, lag e destino. |

Mutação de incidente/plano/aprovação/execução usa SPEC-014. APIs acima são proposta EICT, não endpoints Langfuse.

## Envelope de resposta
data; pagination.next_cursor; meta.as_of; meta.source_watermarks; meta.partial; meta.missing_sources; meta.sampled; meta.coverage; meta.policy_version; meta.timezone; meta.correlation_id.
NULL não vira zero. Métricas com denominador zero são N/A. UI informa recorte parcial por permissão sem revelar ativos proibidos.

## Atualização e concorrência
SSE entrega ao menos uma vez; cliente deduplica por event_id e respeita sequence por entidade. Last-Event-ID permite retomada dentro da retenção do stream; fora dela, carregar snapshot novo. Backoff com jitter e polling de 30 s como fallback. Mudança de tenant encerra stream e limpa cache. Configurações usam ETag/If-Match; conflito 409/412 obriga recarregar diff.

## Segurança
Cookies seguros/httpOnly quando aplicáveis; CSRF em mutações; CSP; escape de Markdown e logs; links allowlisted; sem secrets em browser, URL, logs ou cache. Egress e chamadas Langfuse somente no backend. Authorization scope faz parte da chave do cache, incluindo revisão de acesso; revogação invalida sessão/projeção cacheada. Exportação tem prazo e download autenticado.

## Modelos de acesso sugeridos
Viewer: métricas autorizadas. Operator: triagem e proposta. Approver: decidir no próprio escopo. RemediationExecutor: identidade técnica sem login humano. DomainAdmin: configurar domínio sem autoaprovar ações. PlatformAdmin: infraestrutura/configuração, sem leitura automática de payload. Auditor: trilha redigida. PayloadReader: concessão específica temporal.
Roles combinam com tenant, domínio, ambiente, classificação e SoD.

## Metas iniciais e testes
Listagem de 50 linhas; limite máximo 200; consultas grandes em jobs assíncronos. API p95 até 2 s para recorte de 24h em carga acordada. Testar 100 usuários concorrentes e 50 mil atividades/dia no piloto como hipótese de dimensionamento, não benchmark medido. Testar autorização em agregados, export, busca, SSE, deep links e cache.

