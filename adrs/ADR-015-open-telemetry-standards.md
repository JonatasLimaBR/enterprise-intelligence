# ADR-015 — Padrões abertos para telemetria e contratos

- Status: Aceita

## Decisão

Preferir OpenTelemetry para métricas/logs/traces, CloudEvents para envelope de eventos, OpenAPI/AsyncAPI para APIs e eventos, JSON Schema/Avro/Protobuf conforme transporte, OpenLineage quando disponível e SBOM CycloneDX ou SPDX.

## Consequências

Reduz lock-in e facilita conectores; nem todas as fontes suportam os padrões completamente.

