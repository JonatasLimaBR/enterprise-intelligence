# SPEC-007 — Agentes, Ferramentas e Handoffs

## Agentes

Supervisor, Incident, RCA, SLA, Spark, Pipeline, Quality, Semantic, Ontology, Model, GenAI, RAG, Code, Security, Cost, Change, Problem, Impact e Action.

## Contrato do agente

Entrada: objective, scope, incident, evidence IDs, constraints, tool budget, time budget, policies e expected schema. Saída: facts, hypotheses, recommendations, confidence, citations/evidence IDs, gaps e requested handoff.

## Tool gateway

- schema validation;
- authentication e authorization;
- argument redaction;
- rate limiting;
- timeout;
- policy decision;
- audit;
- response size limit;
- signed result metadata.

## Memória

- working memory por execução;
- incident memory até encerramento;
- long-term knowledge somente após curadoria/retention policy;
- dados de outro tenant nunca entram no contexto;
- summaries não substituem evidence IDs.

## Proteções

Prompt injection classifier é sinal, não único controle. Ferramentas ignoram instruções em conteúdo recuperado. Allowlist, sandbox, output encoding, taint tracking e least privilege são obrigatórios.

## Handoff schema

`handoff_id`, `from`, `to`, `goal`, `known_facts`, `open_questions`, `evidence_refs`, `actions_attempted`, `constraints`, `deadline`, `confidence`, `return_route`.

## Avaliação

Task completion, factuality, evidence coverage, tool correctness, unsafe action rate, loop rate, cost e latency por agente.

