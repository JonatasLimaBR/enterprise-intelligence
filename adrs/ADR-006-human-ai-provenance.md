# ADR-006 — Proveniência de código humano/IA

- Status: Aceita

## Decisão

Não usar detector estilométrico como prova. Classificar apenas por evidências explícitas: attestations, telemetry autorizada e declaração. Na ausência, `UNKNOWN`. Um sinal `ai_likeness` pode existir para pesquisa, rotulado como não conclusivo e proibido para decisões individuais.

## Motivação

Detectores têm falsos positivos e podem gerar riscos trabalhistas, éticos e reputacionais. O foco do gate é qualidade e segurança do artefato.

## Consequências

Menor promessa de “detecção”, maior defensibilidade e confiança. Requer integração com IDE/agentes e padrão de attestation.

