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

### Camada de contratos (feature EICT_DATA_CONTRACTS — build concluído em 2026-09-22)

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
| Duração do ciclo | ❌ **18,2 min** contra os 10 do critério SC8 — ver abaixo |
| Testes | ✅ **180** (68 novos) · ruff limpo |

**Ciclo:** `bootstrap → collect → medallion → quality → correlate → narrate → dispatch`.

**Custo de execução medido:** as 12 regras rodam em segundos — 2,6s a regra de completeness e
3,8s o join referencial de 60M × 100k, com o warehouse aquecido. A partida a frio custa 27s.

**Por que o ciclo leva 18 min (SC8 reprovado):** cada uma das 7 tasks paga a própria partida
serverless. O ciclo **já levava ~15 min antes desta feature**; a task de qualidade acrescenta
3,5 min, quase todos de inicialização. Correção proposta: fundir as tasks Python numa sessão só,
o que levaria o ciclo para perto de 8 min. Detalhes em
`.claude/sdd/reports/BUILD_REPORT_EICT_DATA_CONTRACTS.md`.

**Armadilhas do Delta encontradas aqui (valem para qualquer mudança futura):**
- Renomear coluna exige column mapping e **muda o protocolo da tabela**. Por isso `subject` foi
  adicionada e preenchida a partir de `job_id`, que segue gravada em paralelo.
- `UPDATE` recusa expressão não determinística: `rand()` não passa; use hash da chave.
- Engolir exceção de migração esconde a falha por ciclos inteiros — sempre logar o inesperado.

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
