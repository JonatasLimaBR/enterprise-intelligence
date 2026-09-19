# SPEC-002 — Contratos de Eventos

## Envelope JSON conceitual

```json
{
  "specversion": "1.0",
  "id": "01J...",
  "source": "databricks/account-123",
  "type": "eict.execution.completed.v1",
  "subject": "job/456/run/789",
  "time": "2026-09-19T12:00:00Z",
  "tenant_id": "tenant-a",
  "environment": "prod",
  "trace_id": "...",
  "classification": "internal",
  "schema_version": 1,
  "data": {}
}
```

## Tipos mínimos

- `asset.discovered`
- `asset.updated`
- `relationship.observed`
- `execution.started|completed|failed`
- `metric.observed`
- `quality.checked|violated`
- `contract.violated`
- `change.committed|deployed|rolled_back`
- `finding.opened|updated|closed`
- `incident.created|updated|recovered|closed`
- `ai.evaluation.completed`
- `agent.tool.invoked|blocked|completed`
- `policy.decision`
- `action.requested|approved|executed|failed|rolled_back`

## Semântica

- entrega pelo menos uma vez;
- consumer idempotente por event id;
- atualização fora de ordem usa event time e entity version;
- evento inválido vai para quarantine com reason code;
- breaking change cria nova major version;
- PII/secrets proibidos salvo schema aprovado e proteção explícita.

## Observabilidade do pipeline de eventos

Lag, throughput, rejection rate, duplicate rate, DLQ depth, schema errors, consumer offset e replay count.

