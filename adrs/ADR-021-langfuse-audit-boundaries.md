# ADR-021 — Langfuse para tracing, ledger para auditoria e billing para custo realizado

Status: aceita para desenho.

## Decisão
Traces IA são exportados ao Langfuse com contexto OpenTelemetry e minimização. Aprovações, decisões de policy e efeitos externos são gravados em ledger/outbox EICT antes da ação. Faturamento continua fonte do custo realizado; somas no Langfuse representam estimativas conforme disponibilidade.

## Motivação
Tracing pode sofrer sampling, latência e perda; ele não pode provar sozinho que uma ação foi autorizada. O mesmo uso de modelo pode aparecer no SDK, Unity Gateway e billing.

## Alternativas
Usar Langfuse como ledger: rejeitado. Reconstruir ferramenta LLM inteira dentro do produto: custo desnecessário. Exportar payload cru e filtrar depois: rejeitado; vazamento já teria ocorrido.

## Consequências
Correlacionar IDs e reconciliar fontes. Exporter indisponível degrada observabilidade; falha do audit obrigatório bloqueia escrita privilegiada. Escolha de edição e fronteira de projeto depende de isolamento/controle disponível. Não tratar tags como barreira de segurança.

