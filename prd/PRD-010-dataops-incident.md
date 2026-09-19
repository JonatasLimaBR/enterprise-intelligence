# PRD-010 — DataOps, Incident e RCA

## Problema

Alertas de pipelines e Spark chegam isolados, sem contexto de dependência, mudança, custo ou negócio. A equipe perde tempo reproduzindo consultas e comparando execuções.

## Usuários

NOC/DataOps, Data Engineers, SRE, gestores de plataforma e owners de produtos de dados.

## Objetivos

- Consolidar saúde de jobs, pipelines, compute, SQL e dados.
- Detectar anomalias e prever SLA.
- Automatizar coleta de evidências e formar RCA assistido.
- Sincronizar incidentes com ITSM.
- Confirmar recuperação técnica e informacional.

## Épicos

### E1 — Execution Intelligence

- Timeline de job/run/stage/task.
- Baseline por dia, horário, versão, volume e classe de compute.
- Runtime, filas, retries, failures, skew, spill, GC, input/output, shuffle e executor loss.
- Comparação com última execução saudável.
- Drill-down do pipeline ao operador/plano.

### E2 — Pipeline Dependency

- DAG, upstream/downstream, estado, atraso e critical path.
- Diferenciar causa no compute de espera/upstream sem dados.
- Previsão de conclusão e SLA breach.

### E3 — Incident Lifecycle

- criação automática/manual;
- deduplicação e agrupamento;
- severidade, prioridade e ownership;
- acknowledge, assignment, escalation, mitigation, recovery e closure;
- timeline imutável;
- comunicação operacional e executiva.

### E4 — RCA

- fatos observados;
- alterações recentes;
- hipóteses ranqueadas;
- evidências pró/contra;
- confiança calibrada;
- testes sugeridos;
- runbook e incidentes semelhantes;
- conclusão humana e feedback.

### E5 — Problem Management

- clusterização por assinatura;
- impacto acumulado;
- criação de problem record;
- known error e workaround;
- ação permanente e verificação de eficácia.

## Regras principais

- Um incidente não deve ser aberto para cada alerta filho do mesmo evento causal.
- Severidade e prioridade são dimensões diferentes: severidade mede efeito; prioridade inclui negócio e urgência.
- Encerramento requer recuperação de serviço e, quando aplicável, validação de qualidade/freshness.
- Hipótese de RCA não pode ser apresentada como causa confirmada.
- Alterações ocorridas na janela causal têm peso, mas correlação temporal isolada não prova causalidade.

## User stories e aceite

### US-01 Detectar regressão de runtime

Como operador, quero ser alertado quando uma execução se desviar do baseline contextual.

Aceite:

- baseline exclui runs falhos/cancelados configuráveis;
- mostra p50/p95, desvio e tamanho da amostra;
- considera sazonalidade;
- permite suppressão aprovada;
- mantém evidência original.

### US-02 Comparar runs

Como engenheiro, quero comparar run atual e saudável.

Aceite:

- código/commit, parâmetros, cluster, volume, plano, schema, libs e custo;
- diferenças destacadas e exportáveis;
- dados ausentes explicitamente marcados.

### US-03 Prever SLA

Aceite:

- ETA e probabilidade de breach;
- intervalo de confiança;
- principais fatores;
- alerta antes do breach conforme lead time;
- medição posterior de precisão.

### US-04 Criar ticket idempotente

Aceite:

- mesma chave de correlação não cria duplicata ativa;
- atualizações sincronizadas;
- falha na integração entra em retry/DLQ;
- link bidirecional persistido.

### US-05 Validar recuperação

Aceite:

- execução saudável;
- qualidade e freshness validadas;
- dependentes críticos atualizados ou exceção registrada;
- janela de observação cumprida.

## KPIs

MTTD, MTTA, MTTR, top-3 RCA hit rate, incident noise reduction, predicted SLA precision/recall, repeat rate e tempo de investigação economizado.

