# Runbooks Iniciais

## RB-001 — Regressão Spark

1. Confirmar baseline, volume e versão.
2. Comparar stage/task distribution.
3. Verificar skew, spill, GC, executor loss e I/O.
4. Comparar plano/config/cluster/commit.
5. Validar join/cardinality e pruning.
6. Testar hipótese em amostra/stage.
7. Aplicar correção controlada.
8. Validar runtime, custo e qualidade.

## RB-002 — Freshness violation

Verificar upstream, última partição, atraso de fonte, timezone, watermark, contratos e dependentes. Nunca reprocessar sem checar idempotência.

## RB-003 — Cost anomaly

Separar volume, preço, tempo, workers, retries, scan, shuffle e mudança de configuração. Confirmar moeda e tags.

## RB-004 — Agent tool blocked

Preservar evidência, confirmar policy, origem do input, tentativa de injection e escopo da credencial. Não liberar permissão ampla como workaround.

## RB-005 — Secret detected

Bloquear exposição, revogar/rotacionar imediatamente, remover de histórico conforme procedimento aprovado, identificar uso e revisar logs. Tratar segredo como comprometido.

## RB-006 — Connector lag

Checar credencial, quota, cursor, schema change, endpoint, DLQ e backpressure. Reprocessar com janela explícita e idempotência.

