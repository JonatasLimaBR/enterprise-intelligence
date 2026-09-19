# Guia de Engenharia

## Repositório sugerido

```text
apps/web
services/api
services/correlation
services/graph
services/agent-orchestrator
services/action-gateway
connectors/
packages/domain
packages/events
packages/policies
schemas/
infra/
tests/
docs/
```

## Práticas

- trunk-based ou branches curtas;
- conventional commits e PR template;
- contract tests para connectors;
- migrations backward-compatible;
- feature flags;
- semantic versioning de APIs/eventos;
- deterministic core, probabilistic assistant;
- ownership por módulo;
- dependências pinadas e SBOM.

## Definition of Done

- requisitos/aceite atendidos;
- unit, integration, contract e security tests;
- observability e runbook;
- policy/permission revisada;
- documentação e migration;
- performance budget;
- rollback testado quando material;
- threat model atualizado se trust boundary mudar.

## Ambientes e dados

Dados sintéticos por padrão. Produção não é copiada para desenvolvimento sem processo aprovado. Secrets somente por manager. Test tenants isolados.

## Logging

Structured logs com trace, tenant pseudonymized, component, event/action id e error code. Proibido logar prompt completo, token, secret, PII ou payload de negócio sem política específica.

## Erros

Categorias: validation, authentication, authorization, dependency, timeout, conflict, rate_limit, policy_denied e internal. Retry apenas quando seguro; comandos usam idempotência.

