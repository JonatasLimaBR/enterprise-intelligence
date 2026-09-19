# Plano de construção e validação — Portais e Langfuse

## Entregas incrementais

1. Foundation: shells /ops e /admin, identidade, escopos, design system, estados vazios/erro, roteamento e mock fixtures identificadas como sintéticas.
2. Ledger/read models: instrumentar todas as classes ActivityRecord e criar central de ações, incidente e timeline; snapshots e SSE.
3. Administração: connectors, ITSM, roles, policies, approvals/runbooks e auditoria de configuração.
4. Langfuse spike: validar deployment/SDK/edição, isolamento e masking; instrumentar uma interação e uma tool read-only; medir overhead.
5. Observabilidade ampliada: supervisor, handoffs, retrieval/modelos, trace links, uso/custo sem duplicação e exporter health.
6. Remediação sandbox: plano → autorização → execução → recuperação → sync; testar efeitos incertos e rollback.
7. Dashboards: KPIs canônicos, drill-down, freshness, access-aware cache/export e testes de conciliação.
8. Domínios restantes: ampliar telas segundo SCREEN-CATALOG, depois piloto real com limites e owners.

## Dependências para integração real

Repositório/projeto de aplicação; IdP e tenants; decisão Langfuse Cloud/self-hosted; acesso a projeto/endpoint e secret manager; ITSM sandbox; integrações Teams/WhatsApp; ambiente de validação; owners das métricas; versão SDK/API; SLOs e budget. São insumos de implementação futura, não bloqueiam este kit documental.

## Testes de integração obrigatórios

| Cenário | Evidência de sucesso |
|---|---|
| Ação humana e de agente | Ambas aparecem com ator e mesma correlação no painel. |
| Evento duplicado/fora de ordem | Estado e totais corretos, histórico preservado. |
| Reconexão SSE | Sem perder eventos dentro da janela; resnapshot fora dela. |
| Mudança de tenant | Cache e stream anteriores removidos, ACL reavaliada. |
| Exportação após revogação | Download negado e auditado. |
| Langfuse indisponível | Alerta independente e ação ainda rastreável no ledger. |
| Audit store indisponível | Nova execução privilegiada bloqueada. |
| Token em SDK + gateway | Uma chamada não vira duas cobranças no relatório. |
| Payload sintético com secret | Redaction antes do envio; sem valor no destino. |
| Trace amostrado | Dashboard explica cobertura; ledger permanece completo. |
| Política/admin concorrente | Conflito explícito, sem sobrescrever edição. |
| Loop/tool denial | Trace correlacionado e finding visível, sem ampliar privilégios. |
| Fechamento com freshness inválida | Bloqueado por backend e explicado na UI. |

## Definition of Done

Rotas prioritárias conectadas a APIs reais no ambiente de teste, sem mocks silenciosos; autorização negativa validada; qualidade dos KPIs conciliada; navegabilidade/acessibilidade revisada; overhead e lag medidos; runbooks e rollback de configuração documentados. Antes disso, rotular telas como protótipo/especificação conforme estado real.
