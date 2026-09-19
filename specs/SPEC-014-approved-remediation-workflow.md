# SPEC-014 — Contrato técnico de remediação aprovada

## Princípios

Policy decide; humano aprova o plano; executor executa; verificador mede; ITSM registra. Agente não aprova a própria ação nem declara recuperação sem evidência. Todas as entidades têm tenant, versão e trilha de auditoria.

## Entidades

### RemediationPlan

`plan_id`, `incident_id`, `ticket_ref`, `version`, `plan_hash`, `runbook_id/version`, `artifact_digest`, `target_ids`, `environment`, `typed_parameters`, `precondition_snapshot`, `risk`, `estimated_cost`, `maximum_cost`, `execution_window`, `timeout`, `verification_checks`, `observation_window`, `rollback_plan`, `compensation_plan`, `approval_requirements`, `expires_at`.

Hash calculado sobre representação canônica do plano completo. Alterações de parâmetros, alvo, runbook, limites ou contingência criam nova versão e invalidam decisões anteriores. Dados secretos são referências, nunca valores no plano.

### ApprovalDecision

`approval_id`, `plan_id/version/hash`, `approver_principal`, `authority_scope`, `decision`, `reason`, `decided_at`, `expires_at`, `revoked_at`, `authentication_context`, `policy_id/version`, `nonce`.

### ExecutionAttempt

`execution_id`, `plan_hash`, `idempotency_key`, `lease_id`, `fencing_token`, `workload_identity`, `external_operation_id`, `started_at`, `heartbeat_at`, `finished_at`, `step_results`, `status`, `redacted_evidence_refs`.

### RecoveryVerification

`verification_id`, `execution_id`, `check_results`, `baseline_refs`, `health`, `quality`, `freshness`, `downstream`, `observation_start/end`, `verdict`, `limitations`, `verified_at`.

## Estados e transições

| Origem | Condição | Destino |
|---|---|---|
| DRAFT | Plano completo e policy permite proposta | AWAITING_APPROVAL |
| AWAITING_APPROVAL | Quórum de aprovadores elegíveis | APPROVED |
| AWAITING_APPROVAL | Rejeição ou expiração | REJECTED / EXPIRED |
| APPROVED | Snapshot mudou ou aprovação revogada | INVALIDATED |
| APPROVED | Preflight válido e lock adquirido | EXECUTING |
| EXECUTING | Todas as etapas concluídas | VERIFYING |
| EXECUTING | Efeito incerto após timeout | RECONCILING |
| EXECUTING / VERIFYING | Falha e rollback autorizado/seguro | ROLLING_BACK |
| ROLLING_BACK | Reversão confirmada | ROLLED_BACK |
| Qualquer fase ativa | Sem caminho seguro ou permissão | BLOCKED / ESCALATED |
| VERIFYING | Checks e janela aprovados | RECOVERED |
| RECOVERED | Política de fechamento e sync concluídos | CLOSED |

REJECTED, EXPIRED, ROLLED_BACK e ESCALATED encerram a tentativa, não o incidente. RECOVERED não equivale a CLOSED.

## Preflight obrigatório

1. Validar tenant, identidade e autoridade atual de todos os aprovadores.
2. Confirmar plano/hash, expiração, revogação e janela.
3. Reavaliar policy atual; aprovação antiga não sobrepõe restrição nova.
4. Conferir versão/configuração/schema dos alvos e pré-condições.
5. Checar manutenção, freeze, capacidade, limites financeiros e dependências.
6. Obter lock com lease e fencing token por recurso conflitante.
7. Persistir intenção de execução e evidência auditável antes do efeito externo.
8. Emitir credencial curta com privilégio mínimo ao executor.

Falha de autorização/audit/preflight é fail-closed. Não elevar privilégios nem alterar plano para ultrapassar o bloqueio.

## Executor e consistência

Runbooks allowlisted, versionados e assinados; argumentos tipados; nenhuma execução de texto livre retornado por LLM. Restringir rede e duração. Persistir step results e external operation IDs. Idempotência local evita despacho duplicado, mas não garante exactly-once na API externa: se ela não suportar chave idempotente, consultar o estado da operação antes de repetir. Em efeito desconhecido, reconciliar ou escalar, não repetir cegamente.

Timeout/cancelamento não prova que o comando parou. Kill switch bloqueia novos despachos; operações em andamento param apenas em pontos seguros ou via mecanismo do provedor. Renovação de lease sem sucesso bloqueia novos steps. Processo substituto usa fencing token para impedir concorrência obsoleta.

## Aprovação em canais

Card/mensagem apresenta chamado, ação exata, escopo, risco, duração estimada, custo, janela, rollback e expiração. Link opaco abre sessão corporativa autenticada; token do link sozinho não concede autoridade. Callback verifica assinatura, nonce, timestamp e replay. Exigir MFA/step-up conforme risco e SoD para mudanças críticas. Não confiar em número de telefone, display name ou mensagem encaminhada.

## Validação pós-correção

Checks versionados: disponibilidade, erros, latência, runtime, integridade, freshness, reconciliação de contagens, qualidade e downstream aplicáveis. Cada um define consulta, limite, janela e resultado esperado antes da aprovação. Guardar valores antes/depois e freshness da própria medição. Falta de telemetria => inconclusivo, não sucesso. Verificar ausência de efeitos colaterais e observar por janela configurada.

## Rollback e compensação

Rollback não é sempre possível. Distinguir reversão de configuração de reparação de dados já escritos. Plano precisa declarar passos, escopo, validação, riscos e autorização da contingência. Executar somente se pré-condições de segurança permanecem válidas. Caso contrário, congelar a tentativa e notificar. Falha no rollback gera escalonamento com estado parcial preciso; não fechar chamado.

## ITSM e notificações

Transactional outbox com chave `incident_id + execution_id + event_type + sequence`. Publicar plano, decisão, início, steps relevantes, falha, rollback, verificação e fechamento. Preservar precedência de campos e evitar sobrescrever edição humana concorrente. Atualização externa falhou: retry limitado/backoff, DLQ e `sync_pending`; nunca informar fechamento confirmado antes do acknowledgement do ITSM.

Notificação de impedimento contém: motivo/código, etapa, ações efetivamente aplicadas, efeitos conhecidos/desconhecidos, rollback, impacto residual, owner, prazo de escalonamento e próxima ação. Se canal falhar, tentar canal alternativo configurado e registrar falha de entrega.

## APIs propostas

- `POST /v1/incidents/{id}/remediation-plans`: criar rascunho.
- `POST /v1/remediation-plans/{id}/submit`: congelar versão e solicitar autorização.
- `POST /v1/approvals/{id}/decide`: decisão autenticada e idempotente.
- `POST /v1/approvals/{id}/revoke`: revogar antes do despacho; após início acionar cancelamento seguro.
- `POST /v1/remediation-plans/{id}/execute`: uso interno; sempre faz preflight.
- `POST /v1/executions/{id}/cancel`: solicitação de parada segura.
- `GET /v1/executions/{id}`: etapas, evidências e resultado permissionados.
- `POST /v1/incidents/{id}/close`: exige RecoveryVerification válido e política de encerramento.

Erros: `APPROVAL_EXPIRED`, `APPROVAL_REVOKED`, `PLAN_HASH_MISMATCH`, `TARGET_CHANGED`, `POLICY_DENIED`, `RESOURCE_LOCKED`, `EXECUTION_OUTCOME_UNKNOWN`, `VERIFICATION_FAILED`, `ROLLBACK_FAILED`, `ITSM_SYNC_PENDING`. Respostas usam SPEC-003 e não expõem secrets.

## Testes de aceite

- Dois cliques em aprovar não geram duas execuções.
- Aprovação expirada, de outro tenant ou de pessoa sem autoridade falha.
- Mudança de alvo após aprovação exige nova decisão.
- Reinício do worker após chamada externa reconcilia antes de retry.
- Run concluída com freshness inválida não fecha chamado.
- Telemetria ausente mantém verificação inconclusiva.
- Falha de rollback conserva incidente ativo e notifica.
- P1 exige confirmação humana quando policy define.
- Sync ITSM indisponível não repete correção.
- Prompt injection em ticket não altera allowlist ou credencial.
- Revogação e despacho simultâneos são serializados na transação local; se o efeito já começou, acionar cancelamento seguro e informar.
