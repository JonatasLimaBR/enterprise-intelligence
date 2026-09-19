# SPEC-012 — FinOps, Savings e Improvement Engine

## Modelo de dados

### CostRecord

`cost_record_id`, `tenant`, `provider`, `billing_account`, `usage_time`, `service`, `sku`, `resource`, `quantity`, `unit`, `list_cost`, `net_cost`, `amortized_cost`, `currency`, `credits`, `tags`, `invoice_ref`, `source_hash`.

### AllocationRule

`rule_id`, `version`, `priority`, `match_expression`, `target_dimension`, `allocation_method`, `effective_from/to`, `owner`, `approval`.

### CostUnit

`unit_id`, `name`, `numerator_cost_scope`, `denominator_metric`, `grain`, `owner`, `version`.

### Opportunity

`opportunity_id`, `category`, `assets`, `baseline`, `estimated_savings_range`, `confidence`, `implementation_cost`, `risk`, `guardrails`, `recommendation`, `status`.

### ImprovementInitiative

`initiative_id`, `opportunity_refs`, `hypothesis`, `owner`, `change_refs`, `baseline_window`, `measurement_window`, `expected_benefit`, `guardrails`, `result`, `evidence_refs`.

## Reconciliation

Somar registros por invoice/billing scope e comparar à fonte. Diferença acima da tolerância bloqueia chargeback e cria finding. Late-arriving credits podem reabrir períodos conforme policy.

## Allocation methods

- direct tag/owner mapping;
- proportional usage;
- fixed percentage;
- activity-based allocation;
- shared platform pool;
- unallocated.

Ordem e precedência são determinísticas. Uma unidade monetária é alocada uma única vez em cada visão.

## Cost anomaly

Features: custo, uso, volume, runtime, workers, retries, scan, shuffle, model/tokens, schedule e change. Output: expected range, deviation, drivers, related changes, confidence e business context.

## Savings calculation

`gross_savings = comparable_baseline_cost - observed_normalized_cost`

`net_savings = gross_savings - implementation_cost - induced_costs`

Normalizar por volume, sazonalidade, preço e câmbio. Reportar faixa quando incerteza for material.

## Double-count prevention

Oportunidades sobre mesmo asset/janela/driver recebem grupo de exclusão ou dependência. Realização é atribuída por iniciativa aprovada, com reconciliação.

## Recommendation safety

Simular impacto em capacity/SLO quando possível. Não sugerir desligamento de asset com dependência ativa confirmada. Mudança passa por Change Risk Score.

## APIs mínimas

- `GET /v1/finops/summary`
- `GET /v1/finops/costs`
- `GET /v1/finops/anomalies`
- `GET /v1/finops/opportunities`
- `POST /v1/finops/opportunities/{id}/initiatives`
- `GET /v1/finops/initiatives/{id}/realization`
- `GET /v1/finops/unit-economics`
- `GET /v1/finops/forecast`

## Dashboards

Executive cost, domain showback, workload efficiency, anomaly investigation, opportunity funnel, realized savings, AI FinOps e allocation quality.

## Tests

Reconciliation fixtures, currency/credit cases, late events, allocation precedence, zero/negative usage, double counting, volume normalization e guardrail regression.

