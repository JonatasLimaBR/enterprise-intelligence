# PRD-030 — MLOps, LLMOps, RAG e Agentes

## Objetivo

Medir saúde, qualidade, custo, risco e eficácia de sistemas de IA tradicionais e generativos, correlacionando-os aos dados, código, processos e resultados que os sustentam.

## Assets

Modelo, versão, experimento, endpoint, feature, dataset, prompt, template, chain, retriever, embedding model, vector index, documento, chunk, agente, ferramenta, guardrail e avaliação.

## Model Intelligence

- disponibilidade, latência, throughput e erro;
- métricas offline/online específicas;
- data/concept drift;
- feature freshness e qualidade;
- skew treino-serving;
- fairness somente quando aplicável e legalmente aprovado;
- custo por predição e utilização;
- champion/challenger e rollback.

## GenAI Intelligence

- tokens input/output e custo;
- latência por etapa;
- model/provider/fallback;
- task success e satisfação;
- groundedness e citation correctness;
- safety e policy violations;
- PII/secrets;
- prompt/version regression;
- cache e context efficiency.

## RAG Intelligence

- ingestão e idade dos documentos;
- chunking e cobertura;
- falhas de embedding/indexação;
- recall@K, precision@K, MRR/nDCG conforme dataset;
- relevância e diversidade;
- conflitos de fontes;
- geração sem suporte;
- rastreio da resposta até documentos/chunks.

## Agent Intelligence

- plano e etapas;
- ferramentas invocadas;
- taxa de sucesso/erro por tool;
- retries e loops;
- handoffs;
- escalation rate;
- autonomia e approvals;
- efeito real da ação;
- custo, duração e segurança.

## Regras de segurança

- nenhuma entrada externa é tratada como instrução confiável por padrão;
- conteúdo recuperado é dado, não autoridade;
- tools recebem parâmetros validados e identidade de workload;
- dados sensíveis são minimizados/redigidos;
- operações críticas usam aprovação e step-up authentication quando necessário;
- outputs de LLM não alteram o policy engine.

## User stories

### AI-01 Regressão após prompt

Mostrar que escalation rate aumentou após uma versão de prompt, controlando por volume e mix de intenção.

### AI-02 Fonte desatualizada

Identificar queda de qualidade relacionada a documentos vencidos e indicar os agentes/consultas afetados.

### AI-03 Tool misuse

Bloquear tentativa de escrita por agente read-only e registrar prompt, decisão de policy, identidade, argumentos redigidos e resultado.

### AI-04 Drift

Alertar mudança relevante, apresentar teste/métrica, segmento, período, provável impacto e necessidade de avaliação humana.

## Avaliação

Conjuntos dourados versionados, testes offline no CI, amostragem online, avaliação humana cega quando possível, LLM-as-judge apenas calibrado e nunca como evidência única em decisões críticas.

## KPIs

Task success, groundedness, safety pass rate, tool success, mean steps, latency, cost/request, fallback, escalation, drift detection precision e incident rate.

