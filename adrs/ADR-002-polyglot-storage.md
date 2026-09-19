# ADR-002 — Persistência poliglota com fonte de verdade definida

- Status: Aceita

## Decisão

- Event store/lakehouse para histórico e reprocessamento.
- Banco relacional para estado transacional de incidentes, policies e approvals.
- Grafo para topologia/impacto.
- Search index para logs, documentos e investigação textual.
- Object storage para evidências e anexos.
- Vector index apenas para similaridade/recuperação semântica.

Cada entidade possui um sistema de registro explícito; o grafo não substitui o ledger transacional e o vector store não é fonte de verdade.

## Consequências

O desenho otimiza workloads, mas aumenta complexidade operacional. Outbox/CDC e reconciliação mantêm consistência eventual.

