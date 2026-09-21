# Enterprise Engineering & Operations Intelligence

**Uma camada de inteligência sobre as ferramentas que a empresa já tem, que responde o que
elas não respondem: por que isso aconteceu, o que mudou, quem é afetado e quanto custou.**

Este repositório tem duas partes: a **especificação completa** do produto (13 PRDs, 21 ADRs,
17 SPECs, arquitetura, roadmap, UX e governança) e uma **demo executável** que implementa a
primeira fatia dela e roda de verdade num workspace Databricks.

---

## A demo em uma tela

Um job de vendas que rodava em minutos passou a levar **26**. O Spark UI mostra o número.
A plataforma mostra a causa:

![Incidente com hipóteses e evidências](demo/img/02-rca-evidencias.png)

**Hipótese #1, confiança 0.9, quatro evidências:**

| Evidência | O que diz |
|-----------|-----------|
| Distribuição da chave | Um cliente concentra **40** % das linhas — **24** milhões de **60** milhões |
| Plano de execução | Operador `Window` novo, ausente no run saudável |
| Mudança | O commit que introduziu a janela, com o arquivo alterado |
| Volume | Entrada **não** cresceu — descarta a explicação mais comum |

As hipóteses alternativas continuam visíveis em **0.05**, cada uma com a evidência que a
derruba. Nenhuma inferência passa de **0.9** sem confirmação humana.

E o texto do resumo? Foi escrito por regra: a saída do modelo de linguagem **foi rejeitada**
na validação porque não citou evidências no formato exigido.

---

## O que isso prova

| Afirmação | Como está verificado |
|-----------|----------------------|
| Detecta regressão real | Baseline de execuções saudáveis contra run de **1570** s — fator **5.7** |
| Não gera enxurrada | **2** execuções lentas → **1** incidente, com recorrência na linha do tempo |
| Diagnostica com evidência | **4** evidências, incluindo uma que **descarta** hipótese concorrente |
| Liga técnica a negócio | **3** ativos afetados via lineage do catálogo, incluindo um painel |
| Mede custo | **0.0682** dólares de custo incremental, vindo da tabela de faturamento |
| Não inventa | Fonte ausente aparece como indisponível; LLM sem evidência é descartado |
| É software, não slide | **100** testes, **96** % de cobertura no núcleo de domínio |

Todos os números acima saem de `demo/numbers.json`, gerado por consulta às tabelas.
Um verificador (`demo/verify_demo.py`) falha se qualquer documento citar número sem origem.

---

## Rodar a demo

### Pré-requisitos
- Workspace Databricks (a demo foi validada em ambiente **somente serverless**)
- Databricks CLI autenticado: `databricks auth login --host <url> --profile <perfil>`
- Python 3.11+

### Passo a passo

```bash
git clone https://github.com/JonatasLimaBR/enterprise-intelligence.git
cd enterprise-intelligence

# 1. testes do núcleo, sem nuvem
cd eict-platform
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest -q

# 2. descobrir o warehouse
databricks warehouses list --profile <perfil>

# 3. implantar a plataforma
databricks bundle deploy -t dev --profile <perfil> \
  --var="warehouse_id=<id>,github_repo=<owner/repo>"

# 4. implantar e rodar o workload encenado
cd ../eict-demo-workload
databricks bundle deploy -t dev --profile <perfil> --var="warehouse_id=<id>"
databricks bundle run generate_data -t dev --profile <perfil> --var="warehouse_id=<id>"
bash scenario/run_scenario.sh        # forma o baseline e provoca a regressão

# 5. correlacionar e abrir o console
cd ../eict-platform
databricks bundle run eict_cycle -t dev --profile <perfil> --var="warehouse_id=<id>"
databricks bundle run eict_console -t dev --profile <perfil> --var="warehouse_id=<id>"
```

O cenário completo consome algumas horas de compute serverless. Para apresentar sem
reproduzir tudo, use o kit em [`demo/`](demo/README.md): congela o estado real e restaura
em segundos.

---

## Como funciona

```text
job monitorado ──► Jobs API + run profile + GitHub
                        │
            bronze ──► silver ──► gold (features por execução)
                        │
            correlator (Python puro, sem Spark)
              baseline → detecção → comparação → hipóteses por regra
              → incidente idempotente → lineage → custo
                        │
            narrador (LLM) → validação de evidências → console
```

**O princípio que organiza tudo:** o ranking é determinístico e auditável; o modelo de
linguagem só redige, e apenas citando evidências que existem. Detalhes e trade-offs em
[`demo/ARQUITETURA.md`](demo/ARQUITETURA.md).

---

## Estrutura

| Diretório | Conteúdo |
|-----------|----------|
| `demo/` | Roteiro, scripts de reset e gatilho, deck, arquitetura da demo |
| `eict-platform/` | A plataforma: domínio, adapters, jobs, pipeline, console |
| `eict-demo-workload/` | O job encenado que produz a regressão |
| `prd/`, `adrs/`, `specs/` | Requisitos, decisões e contratos técnicos |
| `architecture/`, `engineering/` | Visão de arquitetura, testes, CI/CD |
| `security/`, `governance/`, `operations/` | Ameaças, LGPD, ontologia, SLOs, runbooks |
| `roadmap/`, `ux/` | Fases de entrega e catálogo de telas |

Leitura recomendada da especificação: `CONTEXT.md` → `prd/PRD-000-master-product.md` →
`architecture/ARCHITECTURE.md` → `roadmap/ROADMAP.md`.

---

## O que a demo ainda não faz

Dito em voz alta, porque limite declarado vale mais que promessa: não há remediação
automática, gestão de problemas recorrentes, qualidade de dados nem contratos. O ticket em
ITSM está implementado mas não configurado. O mapa pergunta a pergunta está em
[`demo/PERGUNTAS.md`](demo/PERGUNTAS.md).

**Uma observação sobre o processo:** **8** dos problemas mais relevantes só apareceram
executando de verdade — inferência de tipo no Spark, coluna ambígua, fuso horário, formato
de resposta do modelo. Nenhum teste local os teria encontrado, e todos viraram teste depois.
