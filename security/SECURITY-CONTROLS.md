# Catálogo de Controles

| Área | Controles mínimos |
|---|---|
| IAM | SSO, MFA, RBAC+ABAC, JIT/JEA, SoD, access reviews. |
| Workloads | Identidade própria, credenciais curtas, least privilege. |
| Data | Classificação, encryption, masking, DLP, retention, deletion. |
| Network | Private connectivity quando possível, egress allowlist, WAF. |
| Code | SAST, review, branch protection, signed commits opcional. |
| Supply chain | SCA, SBOM, provenance, assinatura, registry policy. |
| Cloud/IaC | IaC scan, policy as code, drift detection. |
| AI | model allowlist, prompt protection, tool policy, evaluations. |
| Runtime | EDR/runtime detection, rate limit, circuit breaker. |
| Audit | Append-only, time sync, tamper evidence, restricted access. |
| Actions | Approval, idempotency, dry-run, rollback, kill switch. |

## Severity e resposta

Critical: exploração provável/impacto grave; bloquear e responder imediatamente. High: prazo curto e compensating control. Medium/Low: risk-based backlog. Exceção exige owner, motivo, controle e expiração.

