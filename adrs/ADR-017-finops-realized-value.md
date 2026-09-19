# ADR-017 — FinOps baseado em custo normalizado e valor realizado

- Status: Aceita

## Contexto

Dashboards de custo frequentemente confundem redução de consumo, créditos, variação cambial e savings estimada. Isso reduz confiança e incentiva otimizações que prejudicam confiabilidade.

## Decisão

Separar custo de lista, líquido, amortizado e alocado; normalizar comparações por volume, preço, moeda e sazonalidade; distinguir savings identificada, aprovada e realizada. Toda otimização preserva guardrails de SLO, qualidade e segurança.

## Consequências

Medição mais defensável e auditável, porém exige billing detalhado, métricas de negócio e janela de validação. Resultados iniciais podem aparecer mais lentamente.

