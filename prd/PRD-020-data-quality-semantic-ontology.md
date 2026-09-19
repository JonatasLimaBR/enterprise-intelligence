# PRD-020 — Data Quality, Semântica, Ontologia e Impacto

## Visão

Transformar metadata técnica em entendimento empresarial governado, permitindo saber se o dado está correto, o que significa e quem/processo depende dele.

## Escopo

- profiling e regras de qualidade;
- data contracts;
- catálogo e ownership;
- lineage técnico e empresarial;
- métricas semânticas versionadas;
- ontologia e knowledge graph;
- análise de impacto e criticidade.

## Requisitos

### DQ-01 Dimensões

Completeness, accuracy, consistency, freshness, uniqueness, validity, timeliness e referential integrity. Cada resultado deve informar regra, amostra/escopo, janela, severidade e owner.

### DQ-02 Contratos

Contrato versionado com produtor, consumidores, schema, compatibilidade, SLO, limites, classificação, retenção e processo de mudança.

### DQ-03 Semantic Registry

Definições de KPIs com fórmula, granularidade, dimensões, calendário, moeda, fonte, owner, status, versão e exemplos. Detectar nomes iguais com definições diferentes e equivalentes com nomes diferentes.

### DQ-04 Ontology Registry

Tipos, relações, cardinalidade, restrições, sinônimos, ownership e versionamento. Relações mínimas: `produces`, `consumes`, `depends_on`, `serves`, `owned_by`, `deployed_as`, `contains_sensitive_data`, `implements_metric`, `supports_process`.

### DQ-05 Impact Engine

Percorrer grafo com limite e direção configuráveis, ponderando criticidade, ambiente, recência e confiança da aresta.

## Cenário de aceite

Ao atrasar `customer_silver`, o sistema mostra:

- doze pipelines downstream;
- quatro dashboards;
- um modelo de recomendação;
- três APIs;
- domínios Marketing, CRM e Financeiro;
- usuários/clientes afetáveis;
- SLAs e processos ameaçados;
- arestas incertas ou desatualizadas.

## Governança

- definições propostas não se tornam canônicas sem aprovação do owner;
- arestas inferidas são distintas das confirmadas;
- conflitos semânticos geram workflow de resolução;
- lineage importado registra fonte e data;
- exclusões lógicas preservam histórico necessário para auditoria.

## Métricas

Coverage de assets, assets com owner, contratos válidos, violações por domínio, tempo de resolução, lineage freshness, semantic conflicts e precisão do blast radius.

