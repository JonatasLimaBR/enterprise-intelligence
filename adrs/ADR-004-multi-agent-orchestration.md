# ADR-004 — Multiagentes especializados com supervisor

- Status: Aceita com limites

## Decisão

Usar supervisor para roteamento e agentes especializados por domínio. Estado canônico fica fora dos agentes. Handoffs usam envelope estruturado. Toda tool call passa por gateway e policy enforcement.

## Regras

- agentes têm orçamento, timeout e ferramentas mínimas;
- outputs estruturados e validados;
- fatos citam evidence IDs;
- loops e delegation depth limitados;
- decisões críticas exigem regra/aprovação;
- execução suporta fallback determinístico.

## Consequências

Especialização e auditabilidade melhores, com custo adicional de orquestração e avaliação.

