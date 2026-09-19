# CONTEXT — Enterprise Intelligence Control Tower

## 1. Origem da ideia

A concepção começou como evolução de um modelo de PMO/sustentação orientado a eventos e mensagens. A primeira necessidade era transformar sinais do Spark e do Databricks em diagnóstico operacional, em vez de apenas repetir gráficos do Spark UI. A visão cresceu para uma aplicação completa de sustentação de Data Platform e, depois, para uma camada de inteligência sobre tudo o que a organização possui: dados, IA, código, aplicações, infraestrutura, processos, pessoas, segurança, custos e conhecimento.

O problema central não é falta de ferramentas. Empresas já possuem Databricks, ADF, Airflow, dbt, Snowflake, SAP, observability, SIEM, Jira, ServiceNow, Git e plataformas de CI/CD. O problema é que cada ferramenta enxerga uma fatia. A EICT correlaciona os sinais e organiza a resposta.

## 2. Perguntas que o produto precisa responder

1. O que está errado ou degradando?
2. Por que isso aconteceu?
3. O que mudou desde a última condição saudável?
4. Qual é o impacto técnico, operacional, financeiro e regulatório?
5. Quem precisa agir e qual é o SLA?
6. Qual ação é recomendada agora?
7. A ação pode ser executada automaticamente ou exige aprovação?
8. Como impedir recorrência?
9. Quais ativos, processos, pessoas e clientes dependem do componente afetado?
10. O código e a configuração que causaram a mudança são seguros e adequados para produção?

## 3. Evolução da visão

### Estágio 1 — DataOps Support

- Spark, jobs, stages, tasks, executors, shuffle, memória, GC e I/O.
- Lakeflow Jobs, ADF, Airflow, dbt e pipelines.
- Data quality, freshness, contratos e SLA.
- Incident, RCA, Problem, Change e Knowledge Management.
- FinOps, capacidade e infraestrutura.

### Estágio 2 — AI + Data Intelligence

- Modelos preditivos, drift, performance e feature freshness.
- GenAI, prompts, tokens, custo, latência, groundedness e guardrails.
- RAG, embeddings, chunking, retrieval e qualidade de fontes.
- Agentes, ferramentas, handoffs, escalonamentos e autonomia.
- Semantic Layer, catálogo, lineage e ownership.

### Estágio 3 — Enterprise Intelligence

- Ontologia empresarial e knowledge graph.
- Aplicações e processos fim a fim.
- Business impact e revenue-at-risk.
- Risco, compliance e decision intelligence.
- Digital twin lógico da organização.

### Estágio 4 — Engineering & Security Intelligence

- Qualidade, segurança e performance de código.
- SAST, SCA, secrets, containers, IaC e supply chain.
- Proveniência de código humano, assistido por IA, gerado por IA ou desconhecido.
- Change Risk Score, blast radius e gates de implantação.
- Segurança de agentes, modelos, dados e ações automatizadas.

## 4. Objeto central: evento correlacionado

Tudo entra como observação imutável: execução, log, métrica, mudança, alerta, violação, vulnerabilidade, feedback, deploy ou fato de negócio. O motor normaliza esses sinais em eventos e os correlaciona em entidades operacionais:

- `Incident`: interrupção ou degradação.
- `Risk`: condição com potencial de impacto.
- `Problem`: causa ou padrão recorrente.
- `Change`: alteração planejada ou detectada.
- `Violation`: quebra de contrato, política ou controle.
- `Recommendation`: proposta explicável e priorizada.
- `Action`: atividade manual ou automatizada, com autorização.

## 5. Exemplo Spark que motivou o produto

Um job normalmente executa em 18–22 minutos e passa a levar 57 minutos. A maior partição chega a 39,2 GB e a mediana fica em 2,1 GB. Há spill de 41 GB e memória de executor em 93%. O Spark UI mostra esses números; a plataforma deve correlacionar:

- stage e operador afetados;
- `join customer_id` como provável origem;
- diferença em relação à última execução saudável;
- commit que inseriu novo join;
- cardinalidade elevada em 318%;
- ausência de mudança no cluster;
- impacto no dashboard comercial e SLA;
- tempo recuperável estimado;
- custo incremental;
- ação sugerida: AQE skew join, tratamento de chaves dominantes, repartition ou broadcast quando comprovadamente seguro.

O resultado deve ser um RCA com evidências, confiança e alternativas — nunca uma explicação inventada.

## 6. Sustentação fim a fim

O sistema deve acompanhar o incidente desde detecção até aprendizado:

1. Detectar anomalia.
2. Deduplicar e correlacionar sinais.
3. Identificar serviço, dados e processo impactados.
4. Calcular severidade e prioridade de negócio.
5. Prever violação de SLA.
6. Criar ou sincronizar ticket.
7. Identificar owner e squads dependentes.
8. Investigar mudanças recentes.
9. Gerar hipóteses de RCA e evidências.
10. Recuperar runbooks e incidentes semelhantes.
11. Recomendar ou executar ações autorizadas.
12. Manter timeline e comunicação executiva.
13. Confirmar recuperação com métricas e qualidade de dados.
14. Produzir postmortem e ação preventiva.
15. Atualizar conhecimento e padrões de recorrência.

## 7. Domínios funcionais consolidados

### Data Platform

Pipelines, jobs, tabelas, Spark, SQL, warehouses, streaming, lineage, qualidade, contratos, catálogo, compute, capacity e custo.

### AI Platform

Model registry, endpoints, features, drift, performance, experimentos, prompts, modelos fundacionais, RAG, vector stores, agentes, ferramentas e avaliações.

### Business

Processos, clientes, produtos, contratos, receita, margem, SLA, risco e decisões.

### Engineering

Repositórios, commits, PRs, testes, cobertura, complexidade, duplicação, smells, dependências, IaC, pipelines de entrega e provenance.

### Security

Identidade, autorização, posture, vulnerabilidades, secrets, dados sensíveis, supply chain, prompt injection, exfiltração, tool abuse e trilha de auditoria.

## 8. Semântica, ontologia e knowledge graph

A camada semântica define conceitos e métricas: Receita, Margem, Cliente Ativo, Churn, Pedido Entregue. O produto deve detectar múltiplas definições conflitantes e mostrar quais dashboards, modelos, agentes e pipelines utilizam cada versão.

A ontologia representa relações reais, por exemplo:

- Cliente possui Contrato, realiza Pedido e gera Receita.
- Produto é produzido em Planta, armazenado em CD e entregue por Transportadora.
- SAP gera uma tabela, que alimenta um pipeline, um Data Product, um dashboard, um modelo e um agente.
- Repositório produz artefato, deploy altera serviço, serviço processa dataset e atende processo de negócio.

O knowledge graph permite calcular blast radius e converter um erro técnico em impacto empresarial.

## 9. Qualidade de dados

Dimensões: completeness, accuracy, consistency, freshness, uniqueness, validity, timeliness e integrity. Um job verde não implica dado correto. O sistema deve distinguir:

`JOB SUCCESS != DATA SUCCESS`

Contratos definem owner, schema, versão, SLA, freshness, campos obrigatórios e limites. Violações viram eventos rastreáveis e podem bloquear downstream conforme criticidade.

## 10. IA, GenAI, RAG e agentes

### Model Health

Accuracy ou métricas específicas, drift, latência, custo, disponibilidade, feature freshness, distribuição e fairness quando aplicável.

### GenAI Health

Taxa de sucesso, groundedness, relevância, segurança, latência, tokens, custo, tool-call success, handoff quality, escalonamento, fallback, PII e feedback.

### RAG Health

Cobertura documental, atualidade, qualidade de chunks, indexação, embeddings, recall, precision, MRR/nDCG quando cabível, conflitos entre fontes e citações.

### Agent Security

Cada ferramenta tem escopo, identidade, policy e nível de risco. Um agente read-only não pode atualizar ledger financeiro. Ações irreversíveis exigem controles explícitos e aprovação humana.

## 11. Code Intelligence

O produto avalia maintainability, reliability, tests, security, performance, data practices e documentação. Exemplos:

- Python UDF em caminho crítico Spark.
- função com alta complexidade ciclomática;
- redução de cobertura;
- secrets hardcoded;
- SQL injection e command injection;
- biblioteca com CVE;
- regra cloud `0.0.0.0/0` indevida;
- alteração de repartition de 400 para 40 causando partições gigantes;
- alteração de schema com alto blast radius.

O diferencial é ligar a issue ao contexto: pipeline crítico, volume processado, custo, dependentes e risco de implantação.

## 12. Proveniência humano/IA

Não é cientificamente defensável afirmar autoria por IA somente pela aparência do código. A classificação canônica é:

- `HUMAN_AUTHORED_VERIFIED`: evidência de proveniência humana.
- `AI_ASSISTED_DECLARED`: assistência declarada ou telemetria confiável.
- `AI_GENERATED_VERIFIED`: ferramenta/provenance comprovando geração.
- `MIXED_VERIFIED`: contribuições rastreadas de ambos.
- `UNKNOWN`: evidência insuficiente.

Pode existir `AI-likeness signal`, mas ele deve ser rotulado como inferência não conclusiva, nunca usado sozinho para punição, bloqueio ou avaliação de pessoa.

Código assistido por IA pode receber políticas adicionais: SAST, SCA, secret scan, testes, licença, performance e aprovação humana. O objetivo é garantir qualidade e segurança, independentemente da autoria.

## 13. Segurança e supply chain

Abrange código, dependências, imagens, IaC, secrets, cloud, dados, IA e runtime. O grafo da supply chain relaciona Application → Repository → Artifact → Package → Version → CVE → Deployment.

Com lineage, dados pessoais podem ser rastreados de origem até tabela, pipeline, feature store, modelo, API e agente, apoiando LGPD, auditoria e resposta a incidentes.

## 14. Change Risk Score

Antes do deploy, a plataforma calcula risco a partir de:

- criticidade do serviço e processo;
- arquivos e ativos alterados;
- blast radius;
- alteração de schema/contrato;
- qualidade e cobertura de testes;
- achados de segurança;
- dependência nova;
- provenance de código;
- histórico de falhas do componente;
- janela de mudança;
- rollback e observabilidade disponíveis.

O resultado orienta gates: aprovação adicional, canary, bloqueio, validação de Data Owner ou Security.

## 15. Multiagentes

Um Supervisor orquestra agentes especialistas: Incident, RCA, SLA, Spark, Pipeline, Quality, Model, GenAI, RAG, Semantic, Ontology, Cost, Change, Problem, Code, Security, Impact e Action. O handoff carrega objetivo, evidências, escopo, confiança, ações já tentadas e limites de autorização.

Agentes não são a fonte da verdade. Eles consultam ferramentas e evidências, produzem hipóteses e chamam o policy engine para qualquer ação.

## 16. Canais e War Room

A plataforma pode sincronizar Teams, Slack, e-mail e WhatsApp empresarial. Para P1:

- cria incidente;
- identifica impacto e responsáveis;
- abre sala/canal;
- registra timeline;
- solicita atualizações estruturadas;
- gera comunicação executiva;
- encerra após validação técnica e de dados;
- produz postmortem.

## 17. Indicadores

MTTD, MTTA, MTTR, recorrência, SLA compliance, reliability, freshness, data quality, Spark efficiency, cost efficiency, change failure rate, rollback rate, model drift, groundedness, tool success, vulnerabilities, mean time to remediate, coverage, policy violations e business impact avoided.

## 18. Health Score

O score empresarial consolida dimensões com pesos configuráveis: reliability, performance, data quality, SLA, cost, security, capacity, AI quality, code health e process health. Todo score precisa ser decomponível até as métricas e evidências que o formaram.

## 19. Prioridade recomendada para MVP

Databricks + Spark + Lakeflow Jobs + Unity Catalog + billing/system tables + qualidade + SLA + incident/RCA + change correlation + FinOps, integrando Jira ou ServiceNow. A plataforma começa read-only. Depois incorpora Git/CI, segurança, MLOps/LLMOps, ontologia e processos.

## 20. Decisões éticas e de governança

- Sem vigilância oculta de desenvolvedores.
- Sem declaração categórica de autoria por IA sem prova.
- Sem ações privilegiadas baseadas somente em saída de LLM.
- Sem treinar modelos com dados corporativos sem base legal e aprovação.
- Explicabilidade, contestação e auditoria para scores e bloqueios.
- Minimização, retenção e acesso por finalidade.

## 21. Resultado esperado

Plataforma integrada de engenharia, dados, IA, segurança e operação, com evidência, contexto de negócio e ações governadas.

## 22. Portais completos, monitoramento de ações e Langfuse

O usuário solicitou dashboards para monitorar todas as ações, observabilidade com Langfuse, portal administrativo e portal de visualização cobrindo todo o escopo. O kit passa a incluir PRD-100/110/120, SPEC-015/016/017 e ADR-020/021. Há 52 telas operacionais, 34 administrativas e 20 dashboards especificados, além de telas transversais.

A central de ações acompanha agentes, humanos, tools, integrações, propostas, aprovações, execução, bloqueios, rollback, validação, comunicação e fechamento. Todas as visões conectam tenant, incidente, plano, execução e trace. Langfuse investiga IA; OpenTelemetry/APM cobre serviços; ledger comprova autorização; billing comprova custo. UI mostra atrasos, dados ausentes e cobertura, sem confundir execução concluída com recuperação.

Administração inclui identidades, RBAC/ABAC, fontes, ITSM, canais, agentes/tools, policies, runbooks, budgets, Langfuse, redaction, retenção e auditoria. Recursos Langfuse por edição devem ser validados; tags não substituem isolamento. Esta entrega expande documentação e plano de construção; não instala Langfuse nem publica portais reais.

## 23. Registro consolidado das adições anteriores

- Chamados: abrir/atualizar automaticamente após correlação, classificar prioridade e responder consultas autorizadas de gestores por Teams/WhatsApp (SPEC-011).
- FinOps e melhoria contínua: allocation, showback/chargeback, budgets, unit economics, oportunidades e economia realizada com validação, sem dupla contagem (PRD-070/SPEC-012).
- Tokens e Unity Gateway: consumo/custo por agente, modelo, time e projeto, limites, budgets, roteamento, políticas, MCP/tools e payload logging governado (PRD-080/SPEC-013).
- Remediação: usuário confirmou preparar correção, enviar autorização, executar se aprovada, registrar informações e fechar somente após recuperação comprovada. Se não puder corrigir, comunicar impedimento e encaminhar para humano (PRD-090/SPEC-014/ADR-019).
- A autorização nesta conversa é para atualizar o kit documental, não para efetuar mudanças em produção ou abrir chamados reais.
- Aprovação é autenticada, limitada ao plano versionado e expira; mudança relevante exige reaprovação. Falhas parciais exigem reconciliação/rollback seguro e nunca encerramento indevido.
- Este CONTEXT é consolidação dos trechos disponíveis e decisões, não transcrição literal de mensagens anteriores omitidas da janela.

A solução final é uma **Enterprise Engineering & Operations Intelligence Platform** que entende PEOPLE, CODE, DATA, AI, INFRASTRUCTURE, APPLICATIONS, PROCESS, SECURITY, COST e BUSINESS, conectados por SEMANTICS, ONTOLOGY, LINEAGE e KNOWLEDGE GRAPH.
