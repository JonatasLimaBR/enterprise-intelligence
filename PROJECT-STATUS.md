# Estado de encerramento — EICT (engenharia)

> Fechamento do build das Fases 1 e 2. Consolida o que está pronto, o que falta e por quê, e o
> passo-a-passo exato para finalizar quando o ambiente destravar. Números da demo em
> `demo/numbers.json`; detalhe por feature em `CLAUDE.md` e nos arquivos de `.claude/sdd/archive/`.

| Atributo | Valor |
|----------|-------|
| **Data** | 2026-09-27 |
| **Veredito** | Fases 1 e 2 **completas no código**; deploy e verificação real **bloqueados por fatores externos** |
| **Qualidade** | plataforma **752 testes** · kit **48** · ruff limpo · cobertura do domínio ~96% |
| **Repositório** | `github.com/JonatasLimaBR/enterprise-intelligence` · `main` @ `fb0672c` |

---

## Por que o projeto não pode ser "concluído de verdade" agora

O encerramento pleno (deploy + verificação em produção) depende de três bloqueios **externos**, fora
do alcance da engenharia local:

1. **Cota do workspace** — Databricks **Free Edition** recusa runs desde 2026-09-24 19:11 UTC
   (confirmado de novo em 2026-09-27: `warehouses start` → *"Cannot create the resource, please try
   again later."*). A cota reseta por ciclo mensal.
2. **Credenciais/aprovações pendentes** — template WhatsApp `eict_incident_alert` por aprovar na Meta;
   número de plantão com opt-in; `whatsapp_token` no secret scope; credencial do Jira; auth do CLI
   expirada (`bundle validate` → `invalid_grant`).
3. **Passo manual** — reconhecer no console o incidente de SLA que a janela de verificação abre.

Enquanto (1) não liberar, nada é publicável nem verificável — por construção, não por falta de código.

---

## Ledger de features

Legenda: 💻 código · 🚀 publicado no workspace · ✅ verificado em produção · ⛔ bloqueado.

### Fase 1 — MVP DataOps Databricks (completa no código)

| Feature | Código | Publicado | Verificado |
|---------|:---:|:---:|:---:|
| EICT_DATAOPS_DEMO (evento/runtime/RCA) | 💻 | 🚀 | ✅ |
| EICT_DEMO_KIT (roteiro, reset, verificador) | 💻 | 🚀 | ✅ |
| EICT_DATA_CONTRACTS (7 dimensões) | 💻 | 🚀 | ✅ |
| EICT_IMPACT_ENGINE (lineage, blast radius) | 💻 | 🚀 | ✅ |
| EICT_SEMANTIC_REGISTRY (conflitos, ontologia) | 💻 | 🚀 | ✅ |
| EICT_ROBUST_BASELINE (execução vs setup) | 💻 | 🚀 | ✅ |
| EICT_SLA_RISK | 💻 | ⛔ | ⛔ |
| EICT_AUDIT_RBAC | 💻 | ⛔ | ⛔ |
| EICT_CONNECTOR_HEALTH | 💻 | ⛔ | ⛔ |
| EICT_COST_BASELINE | 💻 | ⛔ | ⛔ |
| EICT_EXECUTIVE_SUMMARY | 💻 | ⛔ | ⛔ |
| EICT_INCIDENT_ACK | 💻 | ⛔ | ⛔ |
| EICT_RECOMMENDATIONS (read-only) | 💻 | ⛔ | ⛔ |
| ITSM (Jira) | 💻 | ⛔ | ⛔ (falta credencial) |

### Fase 2 — Quality, graph e problem (completa no código)

| Feature | Código | Publicado | Verificado |
|---------|:---:|:---:|:---:|
| EICT_PROBLEM_MANAGEMENT (clustering) | 💻 | ⛔ | ⛔ |
| EICT_RUNBOOKS_KNOWLEDGE | 💻 | ⛔ | ⛔ |
| EICT_FINOPS_ALLOCATION (showback) | 💻 | ⛔ | ⛔ |
| EICT_FINOPS_SAVINGS (economia) | 💻 | ⛔ | ⛔ |
| EICT_WAR_ROOM_WHATSAPP (notificação) | 💻 | ⛔ | ⛔ |

Data contracts, Unity Catalog lineage e blast radius (itens do ROADMAP da Fase 2) já constam
verificados na Fase 1 (contratos e impact engine).

---

## Passo-a-passo para finalizar (quando a cota liberar)

1. **Reautenticar o CLI:** `databricks auth login --profile eict`.
2. **Rodar um ciclo** (o bootstrap cria as tabelas e colunas novas de todas as features pendentes):
   `databricks bundle deploy -t dev --profile eict` e um run do `eict_cycle`.
3. **Publicar o App** (deploy do `eict_console`).
4. **Janela de verificação:** `PROFILE=eict WAREHOUSE_ID=6836da016907f9bc ./demo/verify_pending.sh`
   (`--skip-precheck` se o status do App ainda vier do bloqueio antigo). ~34 min / 4 runs; retomável.
   Inclui o **passo manual** de reconhecer o incidente de SLA no console.
5. **Conferir** o resumo executivo e o relatório em `demo/verification_report.md`.

Para o canal WhatsApp especificamente (EICT_WAR_ROOM_WHATSAPP):
- Submeter o template `eict_incident_alert` (utility, pt_BR, 6 variáveis) à Meta e aguardar aprovação.
- Cadastrar número/grupo com opt-in; preencher `destination`/`phone_number_id` e ligar `opt_in` em
  `eict-platform/notifications/whatsapp.yaml`.
- Guardar `whatsapp_token` no secret scope `eict`.
- Rodar `--stages notify` num incidente acima do limiar e conferir a visão "Comunicação" (OPS-49).

Para o ITSM (Jira): preencher `jira_base_url`/`jira_project` e os segredos `jira_email`/`jira_token`.

---

## O que fica para depois deste encerramento

- **Fases 3–5** do ROADMAP (Code/Security, AI/ML/RAG/Agents, Enterprise Intelligence) — não iniciadas.
- **22 decisões** mantidas sem revisão em `.claude/sdd/reports/DECISOES_PARA_VALIDAR_2026-09-24.md`.
- **Rascunhos de runbook** RB-007/008/009 (trocar `status` por PR).

---

## Conclusão

Do lado de engenharia, o build das Fases 1 e 2 está **encerrado e verde** (752 + 48 testes, ruff
limpo, tudo commitado e no `main`). O que resta para o projeto ser dado como concluído em produção não
é código: é o desbloqueio da cota do workspace, a aprovação do template e o provisionamento de
credenciais — e então a execução da janela de verificação acima.
