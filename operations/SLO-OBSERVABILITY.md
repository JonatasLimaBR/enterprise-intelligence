# SLOs e Observabilidade da Plataforma

## SLIs iniciais

- ingestão válida dentro de 60 s;
- disponibilidade API/console;
- tempo de consulta de incidente;
- correlação concluída dentro da janela;
- entrega de notification;
- action execution success;
- connector freshness;
- graph freshness;
- AI response success e grounded evidence coverage.

## SLOs sugeridos

| Serviço | Objetivo mensal inicial |
|---|---:|
| Core API | 99,9% |
| Incident ingestion critical | 99,9% dentro de 60 s |
| Policy gateway | 99,95% |
| Audit write | 99,99% sem perda reconhecida |
| Console query p95 | < 2 s |

## Golden signals

Latency, traffic, errors, saturation, queue lag, DLQ, cache hit, graph traversal, token/cost, connector throttling e policy denials.

## Alerting

Burn-rate multiwindow para SLOs; alertas de capacidade e segurança separados. Dependência LLM degradada ativa modo determinístico.

## Disaster recovery

RPO/RTO por store. Audit e operational store têm prioridade. Testes de restore trimestrais; runbook regional quando aplicável.

