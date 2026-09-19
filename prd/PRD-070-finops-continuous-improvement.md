# PRD-070 — FinOps e Melhoria Contínua

## Visão

Transformar custo de cloud, dados e IA em decisões operacionais explicáveis, ligando consumo a owner, produto, processo, cliente e resultado. O módulo também fecha o ciclo de melhoria: oportunidade → experimento → mudança → validação → benefício realizado.

## Problema

Custos de compute, storage, queries, pipelines, modelos e LLMs aparecem em contas agregadas e tarde demais. Times não conseguem distinguir crescimento legítimo, regressão, ociosidade, falha de arquitetura ou ausência de governança. Recomendações genéricas de redução não demonstram efeito real nem risco operacional.

## Personas

FinOps Lead, Platform/SRE, Data/AI Engineers, Product Owner, Finance, Procurement, CTO/CDO e owners de domínio.

## Objetivos

- Alocar custo a produto, domínio, equipe, ambiente e processo.
- Detectar anomalias antes do fechamento da fatura.
- Explicar custo por drivers técnicos e de negócio.
- Priorizar economia pelo benefício líquido e risco.
- Medir economia realizada, evitando dupla contagem.
- Integrar eficiência financeira à confiabilidade, qualidade e sustentabilidade.

## Capacidades

### F1 — Cost ingestion e normalization

Ingerir billing/usage, preços, descontos, créditos, compromissos, tags, moedas e câmbio governado. Separar custo bruto, líquido, amortizado e alocado.

### F2 — Allocation

Hierarquia configurável: organização → unidade → domínio → produto → aplicação → workload → run/query/request. Custos compartilhados usam regras versionadas e explicáveis.

### F3 — Showback/Chargeback

Showback por padrão; chargeback somente após qualidade mínima de tags/mapeamento, reconciliação financeira e aprovação. Exceções e custos não alocados permanecem visíveis.

### F4 — Anomaly detection

Baseline contextual por workload, schedule, volume, versão, ambiente e sazonalidade. Alertar variação absoluta e relativa, com previsão de fechamento do período.

### F5 — Unit economics

Métricas como custo por run, TB processado, query, cliente, pedido, previsão, documento indexado, resposta GenAI, tool call e resolução de incidente. Cada unidade tem fórmula e owner.

### F6 — Optimization recommendations

- rightsizing e autoscaling;
- pools/serverless/job clusters conforme contexto;
- redução de idle time;
- storage lifecycle/compaction;
- query/file pruning;
- correção de skew/spill/retries;
- schedules e ambientes não produtivos;
- compromissos e descontos sob análise financeira;
- escolha de modelo/roteamento/cache/batching em IA;
- retenção e sampling de telemetry;
- remoção de assets órfãos.

### F7 — Savings lifecycle

Oportunidade → estimativa → aprovação → implementação → janela de medição → validação → realizado/descartado. Baseline, hipótese, custo da mudança e efeitos colaterais são preservados.

### F8 — Forecast e budget

Previsão mensal/trimestral por domínio, budget burn, cenário base/otimista/pessimista e drivers. Alertas de forecast, não apenas budget já ultrapassado.

### F9 — AI FinOps

Tokens, modelo/provider, cache, context size, latency, retries, fallback, embeddings, vector store, evaluation e custo por sucesso de tarefa. Otimização não pode reduzir safety ou qualidade abaixo do SLO.

### F10 — Sustainability proxy

Quando dados confiáveis estiverem disponíveis, estimar energia/carbono com metodologia e confiança explícitas. Não inventar precisão inexistente.

## Regras

- Toda recomendação mostra fórmula, período, moeda, confiança, risco e dependências.
- Economia potencial não é economia realizada.
- Créditos e descontos não ocultam ineficiência técnica.
- Otimização não pode violar SLO, segurança ou data quality.
- Custos compartilhados e não alocados permanecem auditáveis.
- Toda alteração de allocation policy é versionada e recalculável.

## Casos de uso

### FU-01 Regressão de custo

`customer_scoring` passa de US$21 para US$59 por run. Volume cresce 7%, runtime 88%, workers 60% e shuffle 213%. O sistema conclui que crescimento de dados não explica a variação e correlaciona a regressão com mudança de código.

### FU-02 Modelo GenAI caro

Agente usa modelo premium para intenções simples. O sistema simula roteamento híbrido, mede qualidade/latência/custo em dataset controlado e recomenda mudança somente se SLOs forem preservados.

### FU-03 Recurso ocioso

Warehouse/cluster permanece ativo sem utilização significativa. O sistema estima economia líquida, valida restrições e propõe schedule/auto-stop.

### FU-04 Custo não alocado

Billing sem tags entra em bucket `unallocated`, com workflow de ownership e cobertura medida.

## KPIs

- allocation coverage;
- unallocated spend;
- forecast accuracy;
- budget variance;
- cost per unit;
- anomaly precision;
- savings identified/approved/realized;
- realization rate;
- idle waste;
- cost of reliability;
- AI cost per successful task;
- custo evitado por prevenção de incidente.

## Critérios de aceite

1. Total reconciliado com billing dentro da tolerância definida.
2. Toda alocação mostra regra e versão.
3. Anomalia explica principais drivers.
4. Recomendação inclui risco e impacto em SLO/qualidade.
5. Savings realizada usa baseline e janela comparável.
6. Dupla contagem entre oportunidades é impedida.
7. Moeda/câmbio e data de conversão são explícitos.
8. Informações financeiras respeitam autorização.

## Melhoria contínua

Cada melhoria vira `Improvement Initiative` com problema, baseline, hipótese, change, owner, investimento, benefício esperado, guardrails e resultado. Após a janela de validação, o sistema aprende se a recomendação funcionou e atualiza regras sem autoajuste não governado.

