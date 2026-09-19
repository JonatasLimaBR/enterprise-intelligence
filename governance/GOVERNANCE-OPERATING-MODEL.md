# Modelo Operacional de Governança

## Fóruns

- Product Council: visão e priorização.
- Data/AI Governance Council: contratos, semântica e risco.
- Architecture Review: ADRs e platform standards.
- Security/Risk: controles, exceções e incidentes.
- Operations Review: SLOs, recorrência e melhoria.

## Papéis

Product Owner, Platform Owner, Domain Owner, Data Owner, Data Steward, Model/Agent Owner, Security Owner, SRE, Incident Commander e Risk Approver.

## RACI resumido

| Decisão | Responsável | Aprovador |
|---|---|---|
| Data contract | Steward/Producer | Data Owner |
| Semantic metric | Analytics/Data Steward | Business Owner |
| Agent autonomy | AI Owner/Platform | Risk/Security Owner |
| Critical action policy | Platform/Security | CISO/Service Owner |
| Risk override | Change Owner | Designated Approver |
| Incident closure P1 | Incident Commander | Service Owner |

## Cadências

Daily operational review; weekly problem/change review; monthly SLO/cost/quality; quarterly ontology, access e model risk review.

## Governança de políticas

Policies em código, versionadas, testadas, aprovadas e com rollout. Mudança de policy é change crítico conforme alcance.

