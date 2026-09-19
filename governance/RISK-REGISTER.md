# Registro de Riscos

| ID | Risco | Prob. | Impacto | Mitigação | Owner sugerido |
|---|---|---:|---:|---|---|
| R01 | Metadata/lineage incompletos | Alta | Alta | Confidence, stewardship e discovery incremental | CDO |
| R02 | Alert fatigue | Alta | Alta | Dedup, SLO/burn rate, feedback e tuning | SRE |
| R03 | RCA alucinado | Média | Crítica | Evidence-first, labels, deterministic checks | AI/Platform |
| R04 | Ação autônoma danosa | Baixa/Média | Crítica | L0/L1 inicial, policy, approval, rollback | CTO/CISO |
| R05 | Vazamento de PII/secrets | Média | Crítica | Minimização, DLP, redaction, IAM | DPO/CISO |
| R06 | Cross-tenant exposure | Baixa | Crítica | Tenant enforcement e negative tests | Platform |
| R07 | Score opaco ou enviesado | Média | Alta | Versionamento, decomposição, contestação | Governance |
| R08 | AI-code detector usado contra pessoas | Média | Alta | ADR-006, proibição explícita e audit | HR/Legal/CISO |
| R09 | Custo de telemetria excessivo | Média | Alta | Sampling, tiered retention, federated access | FinOps |
| R10 | Lock-in de fornecedor | Média | Média | Canonical model e standards | Architecture |
| R11 | Dependência LLM indisponível | Média | Média | Deterministic fallback e multi-provider option | Platform |
| R12 | Ingestão modifica produção | Baixa | Crítica | Read-only identities e network policy | Security |
| R13 | Ontologia cresce sem governança | Alta | Média | Core mínimo, owner e lifecycle | Data Governance |
| R14 | Métrica financeira inventada | Média | Alta | Source/formula/confidence obrigatórias | CFO/Product |
| R15 | Baixa adoção | Média | Alta | Workflow integration e pilot co-design | Product |

## Revisão

Revisão quinzenal no build, mensal em produção e imediata após incidente material ou mudança de trust boundary.

