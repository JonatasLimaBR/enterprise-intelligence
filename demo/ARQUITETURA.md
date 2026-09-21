# Arquitetura da demo — as decisões e o porquê

Para quem quer saber como funciona por dentro, e principalmente **por que assim**.
Cada decisão traz o contexto que a forçou, a alternativa descartada e o preço pago.

---

## O caminho de um incidente

```text
job monitorado (Databricks)
   │ Jobs API: duração, parâmetros, ambiente
   │ run profile: distribuição da chave + plano físico (instrumentação do workload)
   │ GitHub API: commit, arquivos, trecho relevante do patch
   ▼
bronze.observations ─► silver.runs / changes / run_profiles ─► gold.run_features
   ▼
correlator (Python puro)
   baseline p50/p95 → detecção → comparação com o run saudável
   → hipóteses ranqueadas por regra → incidente idempotente
   → lineage (ativos afetados) → billing (custo incremental)
   ▼
narrador (LLM) → validação de evidence IDs → texto ou fallback determinístico
   ▼
console (Databricks App) + ticket ITSM (quando configurado)
```

---

## Decisão 1 — Domínio sem dependência de plataforma

**Contexto:** a ADR-010 exige que o modelo canônico não conheça a Databricks, para que o
segundo conector (Snowflake, ADF) não obrigue a reescrever a lógica.

**Escolha:** `eict/domain/` é Python puro — dataclasses e stdlib, mais pydantic para a
validação da saída do LLM. Toda tradução vive em `eict/adapters/`.

**Alternativa descartada:** DataFrames circulando pelo domínio. Seria mais direto e
economizaria mapeamento, mas prenderia as regras ao Spark e exigiria cluster para testar.

**Preço:** camada de mapeamento a mais. **Ganho:** as regras de baseline, ranking e
idempotência rodam em milissegundos, sem Spark — e por isso têm 96 por cento de cobertura.
Um teste que varre a árvore sintática falha se alguém importar `databricks` ou `pyspark` ali.

---

## Decisão 2 — Evidência de skew por instrumentação, não por event log

**Contexto:** o plano original lia os event logs do Spark para extrair tamanho de partição,
spill e GC. O workspace acabou sendo **somente serverless**, onde não existe entrega de
logs de cluster, nem SparkContext, nem listener.

**Escolha:** o próprio workload grava um *run profile* em JSON — distribuição da chave de
join e plano físico capturado do `explain`. A plataforma ingere isso como qualquer outra
fonte.

**Alternativa descartada:** `system.query.history`, que exige administrador de conta e não
traz distribuição por partição.

**Preço:** spill e GC passaram a aparecer como indisponíveis, e o workload precisa ser
instrumentado. **Ganho:** a evidência ficou mais forte para o diagnóstico — distribuição da
chave e operador do plano explicam a causa melhor do que o sintoma de spill.

---

## Decisão 3 — A IA redige; as regras decidem

**Contexto:** ADR-004 e ADR-005: a plataforma promete evidência antes de inferência.

**Escolha:** o ranking é determinístico, com pesos versionados por sinal. O modelo recebe os
fatos já numerados e só escreve o resumo. Cada frase precisa citar o identificador de uma
evidência existente; se não citar, a saída é descartada e entra um texto gerado por regra.

**Alternativa descartada:** o modelo gerar e ranquear hipóteses. Mais fluido, impossível de
auditar e sujeito a inventar causa.

**Preço:** o texto às vezes é mais seco. **Ganho:** na execução real, a saída do modelo **foi
rejeitada** e o fallback assumiu — o guardrail se provou em produção, não só em teste.

---

## Decisão 4 — Teto de confiança e evidência contrária

**Escolha:** nenhuma hipótese inferida passa de 0.9; correlação apenas temporal é limitada a
0.5. Hipóteses derrubadas continuam visíveis, com a evidência que as derruba.

**Por quê:** uma ferramenta que mostra só a resposta certa não dá para auditar. Mostrar o que
foi considerado e descartado é o que diferencia diagnóstico de chute — e deixa espaço para o
humano discordar com base no mesmo material.

---

## Decisão 5 — Um incidente por job e tipo, não por alerta

**Escolha:** a chave de correlação combina locatário, job e tipo de problema. Execução lenta
repetida vira nova entrada na linha do tempo.

**Preço:** o segundo run lento não abre incidente novo, então o operador precisa olhar a
linha do tempo para ver a repetição. **Ganho:** é o que mata a enxurrada de alertas — a
regra do PRD-010 de que um evento causal não deve gerar N incidentes.

---

## Decisão 6 — Baseline no domínio, não em tabela

**Contexto:** a exclusão correta depende do run avaliado: só execuções anteriores,
bem-sucedidas, e que não pertençam a um incidente aberto.

**Escolha:** o baseline é calculado em memória pelo domínio, a partir das features.

**Alternativa descartada:** materializar em Gold. Mais rápido em escala, mas a regra de
exclusão vira SQL difícil de testar.

**Preço:** não escala para milhões de execuções sem paginação. **Ganho:** um bug real
apareceu por causa disso — o segundo run lento estava sendo comparado com o primeiro run
lento, e não com um saudável. Corrigir foi trivial porque era Python puro com teste.

---

## Decisão 7 — Estado operacional em Delta, com MERGE

**Escolha:** incidentes, hipóteses e evidências vivem em tabelas Delta, com `MERGE` pela
chave de correlação e linha do tempo somente-append.

**Alternativa descartada:** Postgres/Lakebase, como manda a ADR-002. Seria o certo para
produção, com transações de verdade.

**Preço:** sem constraint única; a idempotência depende de o job rodar em série.
**Ganho:** zero infraestrutura extra para a demo. É um desvio consciente e documentado.

---

## Decisão 8 — Fonte ausente vira "indisponível", nunca estimativa

**Escolha:** uma sondagem de capacidades testa cada fonte antes do ciclo. O que não existe
aparece como indisponível na tela; o custo fica pendente enquanto o faturamento não chega.

**Por quê:** é a regra que mais protege a credibilidade do produto. Estimar silenciosamente
é como um diagnóstico médico com exame que não foi feito.

---

## Decisão 9 — Duas unidades deployáveis, sem código compartilhado

**Escolha:** `eict-platform` (a plataforma) e `eict-demo-workload` (o job encenado) são
bundles independentes. O workload não importa nada da plataforma; a instrumentação do run
profile é código dele.

**Por quê:** se o workload dependesse da plataforma, a demo provaria menos — qualquer cliente
teria que instalar uma biblioteca nossa dentro dos jobs dele.

---

## O que a demo não faz

Vale dizer em voz alta, porque um produto honesto sobre limites é mais confiável: não há
remediação automática, não há gestão de problemas recorrentes, não há qualidade de dados nem
contratos, e o ticket no ITSM está implementado mas não configurado. O `PERGUNTAS.md` mostra
isso pergunta a pergunta.
