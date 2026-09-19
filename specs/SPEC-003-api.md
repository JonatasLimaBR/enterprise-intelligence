# SPEC-003 — APIs e Integrações

## Padrões

REST/OpenAPI para comandos e leitura; webhooks/AsyncAPI para eventos; OAuth2/OIDC; mTLS para integrações sensíveis; pagination cursor-based; idempotency key para writes.

## Recursos

- `GET /v1/health/enterprise`
- `GET /v1/assets/{id}`
- `GET /v1/assets/{id}/dependencies`
- `GET /v1/assets/{id}/impact`
- `GET|POST /v1/incidents`
- `GET|PATCH /v1/incidents/{id}`
- `POST /v1/incidents/{id}/acknowledge`
- `POST /v1/incidents/{id}/hypotheses`
- `POST /v1/incidents/{id}/actions`
- `GET /v1/changes/{id}/risk`
- `POST /v1/changes/{id}/evaluate`
- `GET /v1/findings`
- `GET /v1/data-contracts/{id}`
- `GET /v1/semantic-metrics/{id}`
- `GET /v1/ai-assets/{id}/health`
- `POST /v1/approvals/{id}/decide`
- `GET /v1/audit/events`

## Erros

Problem Details: `type`, `title`, `status`, `detail`, `instance`, `code`, `trace_id`, `retryable`. Nunca retornar stack trace ou secret.

## Autorização

Cada endpoint declara permissions e resource scope. Impact e evidence aplicam filtros por classificação, domínio e tenant. Resumo pode ocultar detalhes sensíveis sem ocultar a existência de um risco quando permitido.

## Rate limit e resiliência

Limites por client/tenant, retry-after, circuit breaker, timeout, bulkheads e webhook signing. Writes são idempotentes.

