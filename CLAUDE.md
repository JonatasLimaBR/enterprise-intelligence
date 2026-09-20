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
- **Testes:** `pytest` — `cd eict-platform && .venv/Scripts/python -m pytest -q` (testes de Spark ficam atrás do marcador `spark`)
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

## Estado da demo (feature EICT_DATAOPS_DEMO)

| Item | Estado |
|------|--------|
| Código | ✅ completo — 63 arquivos nos 2 bundles |
| Qualidade | ✅ ruff limpo · 100 testes · cobertura do domínio 96% |
| Deploy no workspace | ✅ executado (schemas, pipeline, job, App) |
| Cenário fim a fim | ✅ regressão de **5,6×** detectada; RCA com hipótese correta em 1º e confiança 0,90 |
| Console | https://eict-console-dev-7474644308924051.aws.databricksapps.com |
| Pendências | Jira (SC4) e medição de latência SC5 |

**Resultado medido:** baseline de 5 runs (168–280s, p95 276s) contra 2 runs lentos (1.570s e 1.547s) → 1 incidente idempotente, 4 evidências (skew na chave, operador `Window` novo no plano, commit `9872c00`, volume estável), impacto no dashboard AI/BI via lineage e custo incremental de US$ 0,0682. A saída do LLM foi **rejeitada pela validação** e a narrativa caiu no fallback determinístico.

**Restrições do workspace usado na demo:** só compute serverless (sem cluster clássico, sem Spark event logs, Spark confs limitadas — por isso a evidência de skew vem do run profile instrumentado); `system.billing.*` não é legível pelo usuário no editor SQL, mas **é** pela identidade do job — o custo funciona.

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
