# SPEC-005 — Health, Risk e Impact Scores

## Requisitos comuns

Scores 0–100, policy version, timestamp, inputs, weights, normalization, missing-data treatment, confidence e critical overrides.

## Data Platform Health

Peso inicial sugerido, configurável:

| Dimensão | Peso |
|---|---:|
| Reliability | 25% |
| Performance | 20% |
| Data Quality | 20% |
| SLA | 15% |
| Cost | 10% |
| Security | 5% |
| Capacity | 5% |

Se existir evento crítico não mitigado, o score recebe cap configurável, evitando média enganosa.

## Change Risk

Componentes: asset criticality 20, blast radius 15, security 15, test/coverage 10, schema/contract 10, rollback 10, observability 5, change complexity 5, history 5, provenance/policy obligations 5. Provenance de IA sozinho não deve elevar risco; ele aciona verificações quando policy assim definir.

## Business Impact

Calcular faixas: assets/processes/customers, duration, SLA, revenue/cost exposure e regulatory factor. Registrar fórmula e fonte. Quando não houver dados financeiros, usar classificação qualitativa e não inventar números.

## Qualidade de score

Backtesting, estabilidade, monotonicidade quando esperada, análise de bias, taxa de override e concordância com especialistas.

