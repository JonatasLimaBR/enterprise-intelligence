# SPEC-010 — Notificações e War Room

## Política de mensagens

Mensagem contém identificação, severidade, impacto, evidências resumidas, owner, SLA e link. Evitar payload sensível. Agrupar updates para reduzir fadiga.

## Cadências

P1 configurável (ex.: 15 min), P2 (30–60 min), demais sob evento. Sem mudança material, indicar explicitamente em vez de repetir texto.

## Comandos suportados

`ack`, `assign`, `status`, `add evidence`, `request approval`, `resolve candidate`. Ações privilegiadas redirecionam para fluxo autenticado.

## Timeline

Eventos de sistema e mensagens humanas recebem timestamp, ator e source. Edições preservam histórico. Resumo executivo é gerado sobre timeline validada.

## Anti-spam

Dedup, quiet hours configuráveis, severity routing, throttling e subscription preferences. P1 ignora quiet hours somente conforme policy.

