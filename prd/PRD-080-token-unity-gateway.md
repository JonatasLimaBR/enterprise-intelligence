# PRD-080 — Token Intelligence e Databricks Unity Gateway

## Visão

Governar consumo, custo, qualidade e risco de modelos, agentes, MCP servers e tools usando uma camada corporativa de AI Gateway. Na implementação Databricks, integrar o Unity Gateway como plano de controle governado pelo Unity Catalog.

## Contexto Databricks

Unity Gateway registra serviços e assets de IA como securables do Unity Catalog e estende governança às interações de runtime. O produto deve integrar, sem duplicar desnecessariamente, controles de acesso, serviço, tráfego, orçamento, observabilidade e auditoria disponíveis.

## Objetivos

- Medir tokens e custo por usuário, service principal, time, projeto, aplicação, agente, tarefa, modelo e provider.
- Definir budgets, thresholds, hard caps e rate limits.
- Detectar token waste, prompts/contextos excessivos, retries, loops e respostas longas sem valor.
- Correlacionar tokens com sucesso, groundedness, latência e impacto.
- Governar modelos, external providers, agentes, MCP servers e tools.
- Roteamento e fallback seguros, com qualidade observável.
- Auditar interações sem expor conteúdo sensível indevidamente.

## Token Intelligence

### Métricas mínimas

- input/prompt tokens;
- output/completion tokens;
- total tokens;
- cached input/read/write quando informado;
- reasoning tokens quando provider disponibilizar;
- embedding tokens;
- tokens por chamada, sessão, tarefa e usuário;
- tokens desperdiçados em falha/retry/cancelamento;
- tokens por sucesso de negócio;
- context utilization ratio;
- truncation e context-window pressure;
- custo por tipo de token/modelo/provider.

Campos provider-specific permanecem opcionais; ausência é `not_reported`, nunca zero presumido.

## Casos de uso

### TU-01 Explosão de contexto

Agente envia histórico e documentos redundantes, elevando input tokens sem melhorar task success. O sistema identifica o step, compara versões e recomenda summarization, retrieval mais seletivo, caching ou compactação.

### TU-02 Loop de agente

Repetição de tool calls aumenta tokens, duração e custo. Detectar padrão, interromper pelo budget/step limit e abrir finding/incident conforme impacto.

### TU-03 Modelo superdimensionado

Intenções simples usam modelo de maior custo. Simular roteamento para modelo menor; validar quality/safety/latency antes de mudar.

### TU-04 Budget por projeto

Equipe aproxima-se do threshold mensal. Notificar owner, identificar drivers e aplicar hard cap somente se policy permitir e não comprometer processo crítico.

### TU-05 MCP tool governance

Agente tenta acessar tool/servidor MCP sem privilégio ou fora de policy. Unity Gateway/policy bloqueia, e EICT correlaciona o evento ao agente, identidade, incidente e impacto.

## Unity Gateway integration

### Access governance

- Model APIs e external providers;
- registered models;
- foundation model permissions;
- MCP services e tool filtering;
- Unity Catalog functions/custom tools;
- HTTP connections;
- users, groups e service principals.

### Traffic management

- rate limits por serviço/identidade/projeto;
- budgets, thresholds e hard caps;
- traffic splitting;
- fallbacks/failover;
- smart/model routing quando disponível;
- capacity e availability signals.

### Service policies/guardrails

Aplicar policies a request/response conforme conteúdo e principal. A EICT ingere decisões/violações para Security e Incident Intelligence, mas não substitui enforcement do gateway.

### Observability

- requests, token usage e latency via system tables;
- cost attribution por service, target model, principal, service tags e request tags;
- inference tables para payload audit/debug/optimization quando aprovadas;
- status, destination type/name/model e logging errors.

## Privacidade de prompts e respostas

Inference tables podem registrar request/response completos. Habilitação exige finalidade, classificação, catálogo/schema controlado, ACL, masking/redaction, retention e avaliação LGPD. Para muitos cenários, métricas sem payload completo são preferíveis.

## Regras de custo

- separar custo do modelo, gateway/logging e infraestrutura associada;
- considerar inference tables como recurso faturável;
- atribuir por tags/identity e reconciliar com billing;
- distinguir tokens cobrados, reportados e estimados;
- reportar moeda e tabela de preço/version date.

## Alertas

- tokens/request fora do baseline;
- cost/success em degradação;
- loops/retries;
- rate-limit/429;
- budget threshold/hard cap;
- provider/model fallback anormal;
- logging gap;
- uso de modelo/tool não aprovado;
- PII/secret em payload;
- diferença entre usage e billing.

## Critérios de aceite

1. Tokens são atribuídos ao principal, serviço, modelo e tags quando disponíveis.
2. Campos ausentes são explicitamente `not_reported`.
3. Custo por tarefa bem-sucedida é calculável.
4. Budget/rate-limit tem policy, owner e audit.
5. Fallback registra origem, destino, motivo, custo e qualidade.
6. Payload logging respeita aprovação, ACL, masking e retenção.
7. MCP/tool denial é visível sem expor argumentos sensíveis.
8. Token optimization só é recomendada com guardrails de qualidade/safety.

## KPIs

Tokens por successful task, cost per successful task, cache hit/economy, context efficiency, retry/loop waste, budget adherence, fallback rate, rate-limit incidents, policy denial, untagged requests e payload logging coverage aprovada.

## Referências oficiais

- https://docs.databricks.com/aws/en/ai-gateway/
- https://docs.databricks.com/aws/en/ai-gateway/inference-tables

