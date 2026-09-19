# Ontologia e Modelo Semântico

## Core ontology

### Organizational

Organization, BusinessUnit, Domain, Team, Person, Role.

### Business

Process, ProcessStep, Customer, Product, Contract, Order, Revenue, Risk, Control, KPI.

### Technology

Application, Service, API, Repository, Artifact, Deployment, Infrastructure, Connector.

### Data

DataProduct, Dataset, Table, Column, Pipeline, Job, Query, Dashboard, SemanticMetric, DataContract.

### AI

Model, Feature, Endpoint, Prompt, Retriever, VectorIndex, Agent, Tool, Evaluation.

### Operations

Observation, Event, Alert, Incident, Problem, Change, Finding, Action, Runbook, SLO.

## Relações essenciais

`owns`, `operates`, `produces`, `consumes`, `depends_on`, `deployed_as`, `implemented_by`, `reads`, `writes`, `triggers`, `supports_process`, `implements_metric`, `contains`, `contains_sensitive_data`, `affected_by`, `resolved_by`, `supersedes`.

## Temporalidade

Relações têm `valid_from/to` e `observed_at`. O impacto em um incidente histórico usa a topologia válida no momento, não apenas o estado atual.

## Confiança

- 1.0: asserted por fonte oficial ou owner.
- 0.8–0.99: discovered por lineage confiável.
- 0.5–0.79: inferred por correlação forte.
- abaixo de 0.5: candidate, não usada para bloqueios sem confirmação.

## Semântica de métricas

Cada KPI declara nome canônico, sinônimos, fórmula, grain, dimensões, filtros, calendário, timezone, moeda, fontes, owner, status e versionamento. Conflitos são objetos governados.

## Processo de mudança

Proposta → impacto → consulta de consumidores → aprovação → janela de compatibilidade → publicação → depreciação. Breaking change exige nova major version.

