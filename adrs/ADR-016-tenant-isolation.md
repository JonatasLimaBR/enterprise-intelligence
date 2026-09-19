# ADR-016 — Isolamento multi-tenant e domínio

- Status: Aceita

## Decisão

`tenant_id` é obrigatório em dados, chaves, eventos, índices, cache e auditoria. Autorização também considera domain/environment/classification. Clientes que exigem maior isolamento podem usar deployment dedicado.

## Consequências

Permite SaaS e grandes organizações; aumenta rigor de testes e custo de ambientes dedicados.

