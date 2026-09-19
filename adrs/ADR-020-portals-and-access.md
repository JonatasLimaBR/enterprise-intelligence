# ADR-020 — Dois portais com serviços e autorização compartilhados

Status: aceita para desenho.

## Contexto
Gestores precisam de leitura simples e operadores de investigação; administradores configuram políticas que afetam a organização. Misturar tudo na mesma navegação aumenta erros e exposição.

## Decisão
Rotas /ops e /admin em shells distintos com design system comum. Backend aplica RBAC/ABAC em cada recurso, busca, agregação, exportação e stream. Acesso administrativo não implica acesso a conteúdo sensível. Ações operacionais continuam sob SPEC-014.

## Alternativas e consequências
Dois backends independentes duplicariam policy e dados; menu único seria mais simples mas menos claro. Adotar serviços comuns reduz duplicação, exige testes de escopo e invalidação de cache ao revogar acesso. Deploy independente dos shells pode ser adotado sem mudar contratos.

