# ADR-001 — Arquitetura orientada a eventos e modelo canônico

- Status: Aceita

## Contexto

Fontes heterogêneas publicam métricas, logs, mudanças, findings e tickets com formatos, tempos e chaves diferentes.

## Decisão

Usar ingestão orientada a eventos com envelope canônico, schema versionado, idempotência e preservação do payload bruto por retenção controlada. O processamento separa ingestion, normalization, enrichment, correlation e serving.

Campos obrigatórios: `event_id`, `tenant_id`, `source`, `event_type`, `event_time`, `ingested_at`, `asset_refs`, `environment`, `severity`, `schema_version`, `trace_id`, `data_classification` e `payload_ref/hash`.

## Consequências

Maior desacoplamento e replay; exige schema registry, DLQ, ordenação parcial e estratégia de eventos atrasados. Consumers nunca assumem ordenação global.

## Alternativas rejeitadas

Integração ponto a ponto e polling direto pelo dashboard: simples no início, mas frágil e difícil de auditar.

