# ADR-003 — Ontologia versionada e knowledge graph

- Status: Aceita

## Decisão

Adotar ontologia extensível com core mínimo e extensões por domínio. Nós e arestas carregam origem, confiança, validade temporal e status `asserted|inferred|discovered`.

Tipos core: Organization, Domain, Person/Team, Process, Application, Service, DataAsset, Pipeline, Model, Agent, Repository, Artifact, Infrastructure, Metric, Policy, Incident, Change e Risk.

## Trade-offs

Grafo melhora impacto e raciocínio multi-hop; requer governança, resolução de identidade e prevenção de crescimento indiscriminado. Inferências nunca sobrescrevem fatos confirmados.

