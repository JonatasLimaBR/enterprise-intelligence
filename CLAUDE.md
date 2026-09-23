# Enterprise Engineering & Operations Intelligence (EICT)

> Kit de definição de produto e engenharia para uma **Control Tower cognitiva** que correlaciona operação, dados, aplicações, código, segurança, IA, processos, custos e impacto de negócio. Responde: o que aconteceu, por que, qual o impacto, quem deve agir, o que fazer agora e como evitar recorrência. O repositório reúne a documentação (PRDs, ADRs, SPECs, arquitetura, roadmap — ver `MANIFEST.md`) e a **demo executável da Fase 1** em `eict-platform/` e `eict-demo-workload/`.

---

## Stack

Implementado na demo: Python 3.11+, PySpark/Lakeflow, Delta, Databricks Asset Bundles, Streamlit (Databricks Apps), pydantic, pytest/ruff. Stack-alvo completa definida nas ADRs/SPECs:

- **Databricks** como vertical inicial (Lakeflow, Unity Catalog, system tables, billing, Unity Gateway) com core agnóstico via adapters (ADR-010, ADR-018)
- **Arquitetura orientada a eventos** — event backbone, schema registry, DLQ, replay (ADR-001, SPEC-002)
- **Persistência poliglota** — lakehouse/event store, banco relacional, grafo, search index, object storage, vector index (ADR-002)
- **Knowledge graph + ontologia** empresarial (ADR-003)
- **Multiagentes com supervisor** + policy engine determinístico para ações (ADR-004, ADR-007)
- **Langfuse** para observabilidade/avaliação de IA e **OpenTelemetry** (ADR-015, ADR-021)
- Integrações: ITSM (ServiceNow/Jira), Git/CI, scanners SAST/SCA, Teams/Slack
- Tooling local: skills Databricks em `.databricks/aitools/skills/` e `.ai-dev-kit/`

## Estrutura

```
.
├── CONTEXT.md              # contexto longo consolidado (leia primeiro)
├── README.md / MANIFEST.md / GLOSSARY.md
├── TRACEABILITY.md / ACCEPTANCE-CATALOG.md
├── prd/                    # 13 PRDs (PRD-000 master … PRD-120 Langfuse)
├── adrs/                   # 21 ADRs (ADR-001 … ADR-021)
├── specs/                  # 17 SPECs (domínio, eventos, API, RCA, scoring…)
├── architecture/           # ARCHITECTURE, DATABRICKS-REFERENCE, PORTALS-OBSERVABILITY
├── engineering/            # ENGINEERING-GUIDE, TEST-STRATEGY, CI-CD, PORTALS-LANGFUSE-DELIVERY
├── security/               # THREAT-MODEL, SECURITY-CONTROLS, LGPD-AI-GOVERNANCE
├── governance/             # ontologia, operating model, risk register
├── operations/             # SLOs, ITSM, runbooks, melhoria contínua
├── roadmap/                # ROADMAP, BACKLOG, IMPLEMENTATION-PLAN
├── ux/                     # arquitetura de informação, catálogo de 86 telas, contratos críticos
├── templates/              # ADR, incidente, postmortem, data contract (YAML)
├── demo/                   # KIT: roteiro, scripts de reset/gatilho, deck, arquitetura, verificador
├── eict-platform/contracts/  # CONTRATOS: um YAML por dataset, avaliado a cada ciclo
├── eict-platform/          # CÓDIGO: bundle da plataforma (domínio puro, adapters, jobs, pipeline, app)
└── eict-demo-workload/     # CÓDIGO: bundle do job encenado + gerador de dados + cenário
```

## Arquivos-chave

| Arquivo | Função |
|---------|--------|
| `CONTEXT.md` | Origem, evolução da visão (4 estágios) e modelo de evento correlacionado |
| `prd/PRD-000-master-product.md` | Requisitos mestres do produto |
| `architecture/ARCHITECTURE.md` | 10 containers lógicos e fluxo principal |
| `architecture/DATABRICKS-REFERENCE.md` | Referência do vertical Databricks |
| `specs/SPEC-001-domain-data-model.md` | Modelo de domínio canônico |
| `specs/SPEC-002-event-contracts.md` | Contratos de eventos |
| `specs/SPEC-003-api.md` | Contrato de API |
| `specs/SPEC-004-correlation-rca.md` | Correlação e RCA evidence-first |
| `specs/SPEC-014-approved-remediation-workflow.md` | Remediação com aprovação, rollback e verificação |
| `engineering/ENGINEERING-GUIDE.md` | Layout de repositório sugerido e Definition of Done |
| `engineering/TEST-STRATEGY.md` | Pirâmide de testes e 10 cenários dourados do MVP |
| `roadmap/ROADMAP.md` | Fases 0–4 (Discovery → MVP DataOps Databricks → … → AI/ML) |
| `TRACEABILITY.md` | Rastreabilidade PRD ↔ ADR ↔ SPEC |

## Convenções

- **Idioma:** documentação em pt-BR
- **Nomenclatura:** `PRD-NNN-*`, `ADR-NNN-*`, `SPEC-NNN-*`; novas ADRs a partir de `templates/ADR-TEMPLATE.md`
- **Linter:** `ruff` (config em `eict-platform/pyproject.toml`, line-length 120)
- **Testes:** `pytest` — plataforma: `cd eict-platform && .venv/Scripts/python -m pytest -q`; kit: `eict-platform/.venv/Scripts/python -m pytest demo/tests -q`
- **Números da demo:** todos saem de `demo/numbers.json`; `demo/verify_demo.py` reprova documento que cite número sem origem
- **Contratos de dados:** `eict-platform/contracts/*.yaml` no formato de `templates/DATA-CONTRACT-TEMPLATE.yaml`; toda regra exige `owner` e `severity`, senão o contrato inteiro é recusado na carga
- **Databricks:** profile do CLI definido em `~/.databrickscfg` (ex.: `eict`), workspace **só serverless**; sempre passar `--profile eict`
- **Commits (planejado):** conventional commits, trunk-based, SBOM e dependências pinadas

### Princípios não negociáveis

- Evidência antes de inferência; toda afirmação material cita evidence ID.
- IA recomenda; políticas determinísticas autorizam ou bloqueiam.
- Atribuição humano/IA somente com proveniência verificável.
- Complementa ServiceNow, Jira, Databricks, observability e SIEM — não substitui.
- Automação começa read-only e evolui por níveis de autonomia.

## Como rodar

```bash
# Documentação — ordem de leitura recomendada:
# CONTEXT.md → prd/PRD-000 → architecture/ARCHITECTURE.md → roadmap/ROADMAP.md → PRDs/ADRs/SPECs

# Demo (Fase 1) — ver READMEs dos dois bundles:
cd eict-platform && python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -q
databricks bundle validate -t dev --profile eict
databricks bundle deploy   -t dev --profile eict
```

---

## Estado da demo (feature EICT_DATAOPS_DEMO — ✅ Shipped em 2026-09-21)

| Item | Estado |
|------|--------|
| Código | ✅ completo — 63 arquivos nos 2 bundles |
| Qualidade | ✅ ruff limpo · 100 testes · cobertura do domínio 96% |
| Deploy no workspace | ✅ executado (schemas, pipeline, job, App) |
| Cenário fim a fim | ✅ regressão de **5,6×** detectada; RCA com hipótese correta em 1º e confiança 0,90 |
| Console | https://eict-console-dev-7474644308924051.aws.databricksapps.com |
| Pendências | Jira (SC4) e medição de latência SC5 |
| Arquivo do ciclo | `.claude/sdd/archive/EICT_DATAOPS_DEMO/SHIPPED_2026-09-21.md` (fora do versionamento) |
| Kit de apresentação | `demo/` — roteiro (pt/en), deck, one-pager, arquitetura, verificador; ver `demo/README.md` |

### Kit de demonstração (feature EICT_DEMO_KIT — ✅ Shipped em 2026-09-21)

| Item | Estado |
|------|--------|
| Reset do estado | ✅ **20s** medidos (limite 60s) — `reset_demo.sh` restaura snapshot real |
| Números rastreáveis | ✅ 20 fatos em `demo/numbers.json`; verificador reprova número sem origem |
| Roteiro | ✅ 778 palavras, 6 blocos, pt e en com paridade verificada |
| Qualidade | ✅ 25 testes do kit · ruff limpo · 3 capturas pendentes (avisos) |
| Gatilho ao vivo | ✅ 6,5 min com fator 1,84× — SC2 revisto para ≤ 7 min (DEFINE v1.1) |
| Pendências suas | capturar as 3 telas de `CAPTURAS.md`; rodar `prepare_small_job.sh` (~20 min) |

**Por que o critério mudou:** a partida do serverless custa ~150s fixos. Com 10% dos dados o
fator é 1,84× mas o run leva 6,5 min; com 8% cabe em 6 min mas o fator cai para 1,23× e não
gera incidente. O limite original era inalcançável nesta plataforma, então o DEFINE foi revisto
para 7 min com as medições anexadas. Arquivo: `.claude/sdd/archive/EICT_DEMO_KIT/SHIPPED_2026-09-21.md`.

**Resultado medido:** baseline de 5 runs (168–280s, p95 276s) contra 2 runs lentos (1.570s e 1.547s) → 1 incidente idempotente, 4 evidências (skew na chave, operador `Window` novo no plano, commit `9872c00`, volume estável), impacto no dashboard AI/BI via lineage e custo incremental de US$ 0,0682. A saída do LLM foi **rejeitada pela validação** e a narrativa caiu no fallback determinístico.

**Restrições do workspace usado na demo:** só compute serverless (sem cluster clássico, sem Spark event logs, Spark confs limitadas — por isso a evidência de skew vem do run profile instrumentado); `system.billing.*` não é legível pelo usuário no editor SQL, mas **é** pela identidade do job — o custo funciona.

### Camada de contratos (feature EICT_DATA_CONTRACTS — ✅ Shipped em 2026-09-22)

| Item | Estado |
|------|--------|
| Motor de 7 dimensões | ✅ completeness, uniqueness, validity, freshness, volume, schema, referential |
| Execução real | ✅ 12 regras contra 60M linhas; regra mais cara (join referencial) em ~4s com warehouse aquecido |
| `evaluation_error` | ✅ falha de execução nunca vira violação; abre incidente `quality_engine_failure` |
| Incidente por ativo | ✅ `correlation_key` generalizada por `subject` sem mudar a chave de runtime |
| Consumidores | ✅ declarados (contrato) e descobertos (lineage) lado a lado; divergência destacada |
| Quebra reversível | ✅ `break_contract.py` com 4 modos + `restore` (testado: 4,8M linhas quebradas e restauradas) |
| RCA de qualidade | ✅ violação **real** de freshness detectada; `pipeline_failure` em 1º com **0,75** |
| Agrupamento por ativo | ✅ 2 regras violadas em `orders` → **1** incidente com 2 evidências |
| Gate de schema | ✅ coluna removida de `customers` → violação `blocking`, `ratio` 0,667 |
| Uniqueness isolado | ✅ 1.225.417 duplicatas em `orders` detectadas com amostra de chaves |
| Duração do ciclo | ⚠️ **9min44s a 10min16s** em 3 medições (era 18,2) — oscila em torno do SC8 |
| Testes | ✅ **206** · ruff limpo |

**Ciclo:** uma única task Python roda `bootstrap → collect → medallion → quality → correlate → narrate → dispatch`, disparando o pipeline Lakeflow pelo SDK. Uma etapa que falha não derruba as demais; o job falha no fim se alguma falhou.

**Custo de execução medido:** as 12 regras rodam em segundos — 2,6s a regra de completeness e
3,8s o join referencial de 60M × 100k, com o warehouse aquecido. A partida a frio custa 27s.

**Custo do ciclo (3 medições):** as etapas somaram 332s, 402s e 309s; o relógio marcou 9min52s,
9min44s e 10min16s. O correlate caiu de **173s para 96–112s** agrupando as consultas de billing
numa só (`billing_facts`). O que sobra e oscila é o provisionamento do ambiente Python, de ~3 a
~5 min — é ele, e não mais o código, que decide se o ciclo cruza os 10 minutos. Fechar o SC8 com
folga exige atacar o provisionamento (enxugar dependências), não as etapas.

**Lição de estrutura:** o Databricks reaproveita o ambiente entre tasks **consecutivas**. Fundir 7
tasks em 3 *piorou* o tempo (19,8 min), porque o pipeline Lakeflow no meio quebrou esse
reaproveitamento. Uma task só, disparando o pipeline pelo SDK, derrubou para 10,5 min; agrupar
o billing fechou em 9min44s.

**Bugs que só um ciclo com vários ativos revelou** (corrigidos, com teste):
- `persist()` carimbava **todas** as evidências e hipóteses com um `incident_id` tirado
  arbitrariamente de um `set`. Com um incidente por ciclo passava; com quatro, as hipóteses de
  um ativo iam parar no incidente de outro. Agora cada item viaja emparelhado com seu incidente.
- O incidente de `quality_engine_failure` renascia a cada ciclo quando o mesmo ativo também
  tinha violação: a lista de abertos era filtrada só por `subject`, ignorando o `type`.
- O `ratio` da dimensão `schema` era `1/nº de colunas` (maior = pior), invertido em relação às
  demais. Agora é conformidade: colunas íntegras sobre declaradas.
- `pipeline_failure` liderava violações de `schema` e `referential` com 0,50. Produtor parado
  deixa dado velho, não coluna a menos — passou a ser contraditado nas dimensões estruturais e
  caiu para 0,05. Com a coluna `region` removida à mão, a lista passa a ser encabeçada por
  `change_temporal_only` (0,30) — que é a resposta honesta: nada na evidência identifica o autor.

Arquivo do ciclo: `.claude/sdd/archive/EICT_DATA_CONTRACTS/SHIPPED_2026-09-22.md`. A feature 3
do programa (registry semântico, DQ-03/DQ-04) foi entregue em 2026-09-23 — ver abaixo.

### Impact engine (feature EICT_IMPACT_ENGINE — ✅ Shipped em 2026-09-22)

| Item | Estado |
|------|--------|
| Travessia ponderada | ✅ largura com relaxação, profundidade e direção configuráveis |
| Grafo materializado | ✅ `ops.lineage_graph` — **77 arestas**, 33 origens, `first_seen`/`last_seen` |
| Arestas incertas | ✅ **40 das 77 (52%)** sem `entity_type` — marcadas e ponderadas para baixo |
| Score por incidente | ✅ `orders` 1,675 (6 ativos) · `customers` 0,975 (4) · `sales_daily` 0,85 (2) |
| Escada de severidade | ✅ unificada em `domain/severity.py`: info < warning < **high** < critical < blocking |
| Elevação com teto | ✅ **verificada em produção**: `warning → critical` com a aresta gravada |
| `upstream_change` destravada | ⚠️ coberta por teste; exige mudança real de schema a montante |
| Duração do ciclo | ✅ **9min04s**, correlate 90,7–110,8s — dentro da faixa anterior (96–112s) |
| Testes | ✅ **255** (49 novos) · ruff limpo · pureza do domínio mantida |

**O que o motor faz:** percorre `ops.lineage_graph` a partir do ativo ou job do incidente, pondera
cada aresta por recência, confiança, criticidade e ambiente, e agrega um score. Quando o raio
alcança consumo humano (dashboard), eleva a severidade — **no máximo até `critical`**. Só regra
`blocking` do contrato bloqueia: aresta inferida não trava pipeline (ADR-005, ADR-007).

**A travessia busca o melhor caminho, não o mais curto.** Um salto por aresta incerta vale
`0,4 × 0,5 = 0,20`; dois saltos confirmados valem `1,0 × 1,0 × 0,5² = 0,25`. Parar na primeira
visita subestimaria o impacto justamente quando o atalho é o duvidoso.

**A prova mais forte:** a plataforma elevou sozinha um incidente de `warning` para `critical`
porque o raio alcançava o painel comercial a um salto, gravando a aresta que justificou —
*"raio atinge consumo humano em `DASHBOARD_V3/01f1b48…` a 1 salto(s), peso 0.500"*.

**Bug pré-existente corrigido aqui — severidade herdada de problema já resolvido.**
`load_recent_results` carrega 6 horas de resultados e `incident_severity` tirava o máximo sobre
**todas** as avaliações da janela. Um incidente aberto *depois* de a violação ser corrigida nascia
com a severidade dela. `latest_per_rule` reduz à avaliação mais recente de cada regra: a janela
continua tolerando um ciclo sem etapa de qualidade, mas a resposta passa a ser "o que está violado
agora".

Arquivo do ciclo: `.claude/sdd/archive/EICT_IMPACT_ENGINE/SHIPPED_2026-09-22.md`.

**Lacuna fechada pela feature seguinte:** incidentes não se auto-resolviam — ver a auto-resolução
em *Registry semântico* abaixo.

**Armadilhas resolvidas no desenho, antes de custarem um ciclo:**
- O `MERGE` usa `UPDATE SET *` e sobrescreveria `schema_fingerprint` antes de qualquer leitura —
  a mudança de schema upstream seria invisível para sempre. A linha guarda `previous_fingerprint`
  e a comparação mora dentro de `merge_graph`, sem depender da ordem das chamadas.
- `refresh_graph` chegou a rodar **duas vezes por ciclo** ao ligar o correlator de qualidade,
  duplicando `observed_cycles`. Movido para o `main`, com o mesmo grafo passado aos dois.

**Suposição ainda não validada:** `DECAY_PER_HOP = 0,5` é chute fundamentado. Com um grafo de 3
saltos não há base para calibrar. Está isolado como constante versionada.

**Armadilhas do Delta encontradas aqui (valem para qualquer mudança futura):**
- Renomear coluna exige column mapping e **muda o protocolo da tabela**. Por isso `subject` foi
  adicionada e preenchida a partir de `job_id`, que segue gravada em paralelo.
- `UPDATE` recusa expressão não determinística: `rand()` não passa; use hash da chave.
- Engolir exceção de migração esconde a falha por ciclos inteiros — sempre logar o inesperado.

### Registry semântico (feature EICT_SEMANTIC_REGISTRY — ✅ Shipped em 2026-09-23)

Fecha o programa de qualidade (PRD-020, features 1–3).

| Item | Estado |
|------|--------|
| Extração por AST | ✅ `agg`/`groupBy`/`withColumn`/constantes — 18 observações reais, 10 `extraida`, 8 `parcial` |
| Conflito real de `revenue` | ✅ `sales_daily_small.py:33 → F.sum('amount')` × `:49 → F.sum('net_amount')` |
| Incidente `semantic_conflict` | ✅ só divergência bloqueante (fórmula, grão, código × canônica); nasce `warning` |
| Herda o raio | ✅ **verificado em produção**: `warning → critical` pelo painel comercial |
| Auto-resolução | ✅ **3 incidentes fechados no 1º ciclo real**, cada um com entrada `auto_resolved` |
| Ontologia | ✅ `ops.ontology_edges` — 179 arestas, 164 `discovered` (0,85) e 15 `asserted` (1,0) |
| Duração do ciclo | ⚠️ etapa `semantics` custa **10,5–13,6s**; relógio sem fila 9min19s e 9min49s — oscila com o provisionamento |
| Testes | ✅ **331** (76 novos) · ruff limpo · pureza do domínio mantida |

**Como a auto-resolução decide:** `domain/resolution.py` recebe dois conjuntos de
`(subject, type)` — avaliados agora e violando agora — e fecha como `recovered` só o que está
no primeiro e não no segundo. **Ausência de avaliação nunca resolve.** Cada tipo diz o que é
"avaliado": regra com resultado corrente; job cujo run mais recente teve **sucesso** e baseline;
ativo semântico cujos arquivos do `registry.yaml` foram **todos** extraídos.

**Configuração:** a etapa `semantics` lê o repositório de `workload_repo` (variável do bundle,
separada de `github_repo` para não mudar o `collect`) e o registry de `metrics_dir`, passado
explicitamente ao job como `contracts_dir`. Deploy da demo:
`--var=warehouse_id=6836da016907f9bc,workload_repo=JonatasLimaBR/enterprise-intelligence`.

**Bugs que só a auto-resolução revelou** (corrigidos, com teste):
- O correlator de runtime reavalia o histórico inteiro; fechado o incidente, o run lento que o
  abriu **reabria o mesmo incidente** no ciclo seguinte. Já valia para fechamento manual.
  `load_closed_until` marca o que foi julgado.
- Fechado o incidente, o run lento voltava ao baseline e escondia a regressão seguinte.
- Com `sales_daily` em dois arquivos, falhar a busca de um apagaria o conflito e fecharia o
  incidente — por isso "avaliado" exige todos os arquivos.

- `edge_id` da ontologia não incluía a origem; `merge()` preserva a aresta descoberta ao lado da
  afirmada, as duas colidiam e **o MERGE falhava a partir do segundo ciclo** (o primeiro só
  insere). O ship verificou um ciclo só — por isso passou. Corrigido em `97c07b0`; as 179 linhas
  com id antigo seguem na tabela como resíduo inofensivo.

**Baseline sem janela (achado, não corrigido):** `compute_baseline` usa **todos** os runs de
sucesso da história do job. Run lento que não virou incidente fica no baseline para sempre: o job
pequeno tem três runs `heavy` (379s, 284s, 221s), o limiar sobe para ~500s e o run pesado (~390s)
não abre incidente. Por isso o AT-15 não é reproduzível em execução real neste workspace, nem com
`prepare_small_job.sh`. Merece decisão (janela dos N runs mais recentes).

**Pendências:** AT-15 (runtime) coberto só por teste; dois incidentes de `sales_daily` com estado
`resolved`, que não existe no código (gravado à mão em 2026-09-22) — o `reset_demo.sh` os elimina.

Arquivo do ciclo: `.claude/sdd/archive/EICT_SEMANTIC_REGISTRY/SHIPPED_2026-09-23.md`.

---

## Agentes recomendados (agentcode)

| Agente | Quando usar |
|--------|-------------|
| `@brainstorm-agent` | Explorar ideias e abordagens antes de fechar requisitos |
| `@the-planner` | Planejar fases e sequência de implementação |
| `@design-agent` | Transformar PRDs/SPECs em design técnico implementável |
| `@genai-architect` | Supervisor multiagente, handoffs, guardrails (ADR-004, SPEC-007) |
| `@lakeflow-architect` / `@databricks-spark-expert` | Vertical Databricks, ingestão de system tables, Medallion |
| `@data-contracts-engineer` | Contratos de eventos e dados (SPEC-002, SPEC-008) |
| `@schema-designer` | Modelo de domínio, ontologia e grafo (SPEC-001, ADR-003) |
| `@data-governance-auditor` | LGPD, PII, lineage, retenção (ADR-012) |
| `@code-reviewer` | Revisão de qualquer código futuro |
| `@security-reviewer` | Threat model, zero trust, action gateway |

## Comandos úteis

| Comando | Quando usar |
|---------|-------------|
| `/brainstorm` | Explorar uma capacidade antes de especificar |
| `/define` | Capturar requisitos de uma feature a partir dos PRDs |
| `/design` | Gerar DESIGN técnico a partir de um DEFINE |
| `/party` | Discussão multi-especialista sobre decisões de dados |
| `/preflight` | Checagem antes de iniciar implementação |
| `/status` | Relatório de status do projeto |

---

_Gerado por `/start` em 2026-09-19; atualizado pelo `/build` da feature EICT_DATAOPS_DEMO._
