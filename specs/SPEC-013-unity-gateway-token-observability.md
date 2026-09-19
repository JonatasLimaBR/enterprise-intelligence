# SPEC-013 — Unity Gateway e Observabilidade de Tokens

## Adapter scope

O adapter integra metadata/configuração autorizada, usage system tables, billing, audit, service policies, rate limits/budgets e inference tables. Capability discovery evita assumir recursos indisponíveis na região/workspace.

## Modelo normalizado AIUsageRecord

```text
usage_id
tenant_id
request_id
invocation_id
event_time
requester_principal
team/project/application/agent/session/task tags
service_name
destination_type
destination_name
destination_model
provider
input_tokens
output_tokens
total_tokens
cached_tokens
reasoning_tokens
embedding_tokens
token_fields_status
latency_ms
time_to_first_byte_ms
status_code
fallback_from/to/reason
tool_or_mcp_refs
policy_decision_refs
estimated_cost
billed_cost
currency
pricing_version
sampling_fraction
logging_error_codes
payload_evidence_ref
```

## Token extraction

1. Preferir usage fields oficiais da resposta/system table.
2. Normalizar nomes provider-specific.
3. Não estimar quando tokenizer/model version não forem conhecidos.
4. Quando estimar, usar `estimated=true`, método e erro esperado.
5. Reconciliar total quando componentes forem informados.
6. Evitar dupla contagem de request com múltiplas invocations.

## Tags obrigatórias recomendadas

`team`, `project`, `application`, `environment`, `agent`, `use_case`, `cost_center` e `data_classification`. Tags ausentes geram finding de alocação, não bloqueio automático salvo policy.

## Métricas derivadas

- `tokens_per_request`;
- `tokens_per_successful_task`;
- `cost_per_successful_task`;
- `input_output_ratio`;
- `retry_waste_tokens`;
- `failed_request_cost`;
- `fallback_cost_delta`;
- `context_growth_rate`;
- `cache_savings_estimate`;
- `tokens_per_tool_call`;
- `token_budget_burn_rate`.

## Budgets e rate limits

Policy por principal/group/service/project e janela. Estados: healthy, warning, critical, capped. Hard cap deve considerar serviços críticos e fallback behavior; mudanças de cap são auditadas.

## Routing/fallback telemetry

Registrar destination selection, policy/routing version, fallback reason, retries, latency/cost/quality. Comparar resultados para detectar fallback barato porém degradante, ou caro sem benefício.

## Inference tables

### Uso

Debug, monitoring, optimization e compliance. Registros incluem request/invocation IDs, request tags, tempo, status, sampling, latency, request/response, destination e requester conforme disponibilidade.

### Restrições operacionais consideradas

- recurso faturável;
- requer Unity Catalog e privilégios adequados;
- tabela é criada pelo serviço após a primeira request;
- linhas podem levar tempo para aparecer, portanto não servem como único sinal realtime;
- entrega pode ser at-least-once, exigindo dedup por invocation/request;
- payloads acima do limite podem não ser logados e produzem error code;
- certos erros HTTP podem não gerar linha;
- schema/nome não devem ser alterados fora do procedimento suportado.

### Proteção

Catalog/schema dedicado, grants mínimos, row/column controls quando aplicável, redaction downstream, retention curta por padrão e proibição de replicar payload completo ao EICT sem necessidade. Preferir referência governada ao conteúdo.

## Incident rules

- token spike + cost spike;
- repeated 429/rate-limit;
- hard cap interrompendo processo crítico;
- fallback storm;
- tool loop;
- usage sem tags;
- policy denial anomaly;
- inference logging gap;
- suspected PII/secret exposure;
- billing reconciliation mismatch.

## APIs/views

- `GET /v1/ai-usage/tokens`
- `GET /v1/ai-usage/cost`
- `GET /v1/ai-usage/budgets`
- `GET /v1/ai-usage/routing`
- `GET /v1/ai-usage/policy-events`
- `GET /v1/ai-usage/logging-health`

## Validation

Fixtures com multi-invocation, sampled logs, late rows, missing usage, fallback, provider differences, 429, oversized payload e duplicate delivery.

