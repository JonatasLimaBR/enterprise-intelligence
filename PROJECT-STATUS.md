# Estado de encerramento — EICT (engenharia)

> Fechamento do build das Fases 1, 2 e 3. Consolida o que está pronto, o que falta e por quê, e o
> passo-a-passo para finalizar quando o ambiente destravar. Detalhe por feature em `CLAUDE.md` e nos
> arquivos de `.claude/sdd/archive/`; números da demo em `demo/numbers.json`.

| Atributo | Valor |
|----------|-------|
| **Data** | 2026-09-30 |
| **Veredito** | Fases 1, 2 e 3 **completas no código**; deploy e verificação real **bloqueados por fatores externos** |
| **Qualidade** | plataforma **850 testes** · kit **48** · ruff limpo · cobertura do domínio ~96% |
| **Repositório** | `github.com/JonatasLimaBR/enterprise-intelligence` · `main` @ `3e63769` |

---

## Por que o projeto não pode ser "concluído de verdade" agora

O encerramento pleno (deploy + verificação em produção) depende de bloqueios **externos**, fora do alcance
da engenharia local:

1. **Cota do workspace** — Databricks **Free Edition** recusa runs desde 2026-09-24 19:11 UTC. Reseta por
   ciclo mensal.
2. **Credenciais/aprovações pendentes** — template WhatsApp na Meta; número opt-in + `whatsapp_token`;
   `github_token` (SBOM); `jev_api_key` (advisor Jev — e egress desligado por padrão); credencial do Jira;
   auth do CLI (`bundle validate` → `invalid_grant`).
3. **Ações L2 e enforcement** — o executor de remediação (SPEC-014) e o bloqueio físico de CI são decisões
   de segurança/arquitetura próprias, deliberadamente **fora** do build atual.

Enquanto (1) não liberar, nada é publicável nem verificável — por construção, não por falta de código.

---

## Ledger de features

Legenda: 💻 código · 🚀 publicado no workspace · ✅ verificado em produção · ⛔ bloqueado.

### Fase 1 — MVP DataOps Databricks (completa no código)

| Feature | Código | Publicado | Verificado |
|---------|:---:|:---:|:---:|
| EICT_DATAOPS_DEMO · EICT_DEMO_KIT | 💻 | 🚀 | ✅ |
| EICT_DATA_CONTRACTS · EICT_IMPACT_ENGINE · EICT_SEMANTIC_REGISTRY · EICT_ROBUST_BASELINE | 💻 | 🚀 | ✅ |
| EICT_SLA_RISK · AUDIT_RBAC · CONNECTOR_HEALTH · COST_BASELINE · EXECUTIVE_SUMMARY · INCIDENT_ACK · RECOMMENDATIONS | 💻 | ⛔ | ⛔ |
| ITSM (Jira) | 💻 | ⛔ | ⛔ (falta credencial) |

### Fase 2 — Quality, graph e problem (completa no código)

| Feature | Código | Publicado | Verificado |
|---------|:---:|:---:|:---:|
| EICT_PROBLEM_MANAGEMENT · RUNBOOKS_KNOWLEDGE · FINOPS_ALLOCATION · FINOPS_SAVINGS · WAR_ROOM_WHATSAPP | 💻 | ⛔ | ⛔ |

### Fase 3 — Code e Security (completa no nível de decisão)

| Feature | Código | Publicado | Verificado |
|---------|:---:|:---:|:---:|
| EICT_CHANGE_RISK (score de risco por commit) | 💻 | ⛔ | ⛔ |
| EICT_SECRET_SCAN (segredos no diff) | 💻 | ⛔ | ⛔ |
| EICT_SUPPLY_CHAIN (SBOM + advisories) | 💻 | ⛔ | ⛔ |
| EICT_JEV_ADVISOR (recomendação por decisão tipada; ADR-022) | 💻 | ⛔ | ⛔ |
| EICT_ACTION_GATEWAY (deployment gates — decisão + override) | 💻 | ⛔ | ⛔ |

**Fora do escopo (decisão de segurança própria):** executor de remediação SPEC-014 (ação L2 destrutiva —
lease/fencing/rollback) e enforcement físico de CI (bloquear pipeline / commit status).

---

## Passo-a-passo para finalizar (quando a cota liberar)

1. **Reautenticar o CLI:** `databricks auth login --profile eict`.
2. **Deploy + ciclo:** `databricks bundle deploy -t dev --profile eict` e um run do `eict_cycle` (o bootstrap
   cria todas as tabelas/colunas novas — Fases 1–3).
3. **Publicar o App** (`eict_console`).
4. **Janela de verificação (Fase 1/2):** `PROFILE=eict WAREHOUSE_ID=6836da016907f9bc ./demo/verify_pending.sh`
   (~34 min / 4 runs; retomável; inclui o passo manual de reconhecer o incidente de SLA).
5. **Fase 3:** rodar as etapas novas do ciclo — `secret_scan`, `supply_chain`, `change_risk`, `gates`
   (e `jev_advisor` só se ligado). Conferir as visões "Mudanças" e "Gates" no console.
6. **Conferir** o resumo executivo e `demo/verification_report.md`.

Credenciais por canal (todas diferidas hoje):
- **WhatsApp:** template aprovado na Meta + número opt-in + `whatsapp_token`; ligar `opt_in` em `notifications/whatsapp.yaml`.
- **SBOM:** `github_token` no secret scope para o `GitHubClient` inventariar o repo.
- **Jev:** `jev_api_key` + habilitar advisor em `jev/advisors.yaml` (egress off por padrão).
- **Jira:** `jira_base_url`/`jira_project` + segredos `jira_email`/`jira_token`.

---

## O que fica para depois deste encerramento

- **Executor de remediação (SPEC-014)** e **enforcement real de CI** — ações L2, decisão de segurança própria.
- **Fases 4–5** do ROADMAP (AI/ML/RAG/Agents; Enterprise Intelligence) — não iniciadas.
- **Métrica G10** — taxa de aceitação das recomendações do Jev como detector de descalibração no resumo executivo.
- **22 decisões** sem revisão em `.claude/sdd/reports/DECISOES_PARA_VALIDAR_2026-09-24.md`.
- **Rascunhos de runbook** RB-007/008/009 (trocar `status` por PR).

---

## Conclusão

O build das **Fases 1, 2 e 3 está encerrado e verde** (850 + 48 testes, ruff limpo, tudo commitado e no
`main`). O que resta para o projeto ser dado como concluído **em produção** não é código: é o desbloqueio da
cota do workspace, o provisionamento de credenciais e a execução da janela de verificação — mais as decisões
de segurança sobre execução L2 (SPEC-014) e enforcement de CI, deliberadamente deixadas de fora. A Fase 3
entrega tudo o que é construível e seguro no nível de **decisão** (recomenda/decide/registra), respeitando o
princípio não-negociável: **IA recomenda; políticas determinísticas autorizam; execução destrutiva exige
decisão humana e um gateway próprio.**
