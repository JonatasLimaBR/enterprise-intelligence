# PRD-060 — Colaboração, War Room e Automação

## Objetivo

Levar a sustentação ao canal de trabalho, reduzir atualizações manuais e permitir ações seguras, auditáveis e reversíveis.

## Canais

Teams, Slack, e-mail, WhatsApp empresarial, Jira e ServiceNow. Cada conector deve respeitar consentimento, finalidade, retenção e capacidade do canal.

## War Room P1

Fluxo:

1. incidente P1 confirmado;
2. resolução de responsáveis;
3. criação de canal/sala e bridge opcional;
4. resumo inicial com evidências;
5. solicitação periódica de status;
6. timeline automática;
7. resumo executivo em cadência configurável;
8. confirmação de recuperação;
9. postmortem e ações.

## Níveis de autonomia

| Nível | Capacidade |
|---|---|
| L0 | Somente observar e resumir. |
| L1 | Recomendar ação. |
| L2 | Preparar ação e solicitar aprovação. |
| L3 | Executar ações pré-aprovadas de baixo risco. |
| L4 | Orquestrar ações maiores sob policy e supervisão. |

MVP opera em L0/L1.

Evolução L2 aprovada no desenho: PRD-090 e SPEC-014 detalham autorização por plano, execução, validação, atualização/fechamento do chamado e notificação de impedimentos. Não altera a restrição read-only do MVP inicial.

## Requisitos de ação

- identidade de serviço exclusiva;
- escopo mínimo;
- allowlist de comandos/tools;
- validação de parâmetros;
- idempotency key;
- timeout e circuit breaker;
- precondition check;
- dry-run quando possível;
- approval record;
- resultado e evidência pós-ação;
- rollback ou procedimento de compensação.

## Handoff multiagente

Envelope obrigatório: objetivo, incident/risk id, facts, hypotheses, confidence, constraints, tools autorizadas, ações já tentadas, resultado esperado e deadline.

## Aceite

- mensagens não revelam secrets/PII indevidos;
- atualização via canal mantém trilha e autoria;
- duplicatas não criam múltiplas salas;
- ação não autorizada é bloqueada;
- falha do canal não impede operação no console;
- postmortem é rascunho revisável, não documento final automático.
