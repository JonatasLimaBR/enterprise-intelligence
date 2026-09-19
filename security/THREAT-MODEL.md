# Threat Model

## Ativos protegidos

Telemetry corporativa, topologia, dados sensíveis, prompts, código, secrets, identidades, policies, approvals, action credentials, audit e modelos.

## Adversários

Externo, insider malicioso, conta comprometida, dependency maliciosa, tenant vizinho, documento com prompt injection e automação defeituosa.

## Ameaças prioritárias

- spoofing de eventos;
- tampering em evidence/audit;
- cross-tenant access;
- secret leakage;
- prompt/indirect prompt injection;
- tool abuse e privilege escalation;
- data exfiltration via output/canal;
- poisoning do knowledge graph/RAG;
- malicious package/container;
- insecure action/replay;
- denial of service/noisy tenant;
- model provider data retention incompatível.

## Controles

Signed webhooks, mTLS, workload identity, schema validation, append-only audit, tenant scoping, encryption, DLP/redaction, egress allowlist, policy gateway, approvals, idempotency, provenance, SBOM, graph source/confidence, quotas, kill switch e continuous evaluation.

## Abuse cases

### Documento instrui agente a ignorar regras

Conteúdo é tratado como não confiável, não pode modificar system policy; tool call passa por policy gateway.

### Atacante falsifica evento crítico

Verificação de origem/assinatura, nonce/timestamp, allowlist, anomaly e quarantine.

### Operador tenta aprovar própria mudança crítica

Segregation of duties impede self-approval.

### Tenant A consulta grafo B

Tenant obrigatório em query planning e row-level enforcement; testes negativos contínuos.

## Residual risk

LLM pode errar mesmo com grounding. Por isso ações materiais exigem policy, evidência e aprovação proporcional.

