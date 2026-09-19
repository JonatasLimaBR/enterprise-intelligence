# ADR-005 — RCA baseado em evidências e hipóteses

- Status: Aceita

## Decisão

Representar RCA como conjunto de hipóteses, cada uma com evidências favoráveis, contrárias, ausentes, confiança calibrada e testes de confirmação. `suspected` e `confirmed` são estados distintos.

LLM pode organizar e explicar; cálculo de métricas, diffs, lineage e policy é realizado por componentes determinísticos.

## Consequências

Reduz alucinação e melhora revisão. Exige evidence store, IDs estáveis e feedback sobre o resultado verdadeiro.

