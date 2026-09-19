# Plano de Implementação do MVP

## Workstream A — Foundation

- tenant, identity, RBAC/ABAC;
- schemas e event backbone;
- operational store, lakehouse e audit;
- CI/CD, IaC, secrets e observability.

## Workstream B — Databricks connector

- capability discovery;
- jobs/runs/tasks;
- compute/query/billing;
- Unity Catalog assets/lineage/audit;
- checkpoints, backfill e connector health.

## Workstream C — Intelligence

- asset resolution;
- baselines e anomaly features;
- dedup/correlation;
- SLA ETA;
- run comparison;
- impact graph;
- hypothesis/evidence model.

## Workstream D — Experience

- Command Center;
- incident workspace;
- service/asset detail;
- change comparison;
- administration e connector health;
- API/webhooks.

## Workstream E — ITSM e collaboration

- Jira ou ServiceNow;
- notification adapter;
- assignment/ack/status synchronization;
- failure/retry/DLQ.

## Workstream F — Trust

- redaction/classification;
- policy engine;
- prompt/tool guardrails;
- threat testing;
- AI evaluation;
- audit/export.

## Sequenciamento por sprint sugerido

### Sprints 1–2

Foundation, schemas, identity, synthetic dataset, connector spike e UX prototype.

### Sprints 3–4

Databricks ingestion, inventory, run views, baseline v1 e operational store.

### Sprints 5–6

Incidents, correlation, SLA risk, Git changes e ITSM.

### Sprints 7–8

RCA evidence, impact graph, recommendations e executive view.

### Sprints 9–10

Hardening, security, performance, replay, evaluation e pilot.

### Sprints 11–12 opcionais

Quality/contracts, war room e improvements do piloto.

## Pilot

Selecionar 3–5 pipelines com incidentes conhecidos, owners engajados e impacto mensurável. Rodar shadow mode por 2–4 semanas, comparar com operação atual, ajustar thresholds e somente depois tornar alertas oficiais.

## Go-live checklist

- access/security review;
- connector permissions verificadas;
- SLOs/alerts/runbooks;
- retention e privacy;
- support ownership;
- DR/restore test;
- user training;
- dashboard de qualidade dos próprios diagnósticos;
- rollback/desativação do produto sem afetar cargas monitoradas.

