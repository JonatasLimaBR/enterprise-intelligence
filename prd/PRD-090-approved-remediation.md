# PRD-090 — Remediação assistida com aprovação humana

## Escopo e status

Requisito aprovado pelo solicitante para inclusão no produto. Este documento especifica uma funcionalidade futura; não autoriza executar correções em ambientes reais nesta conversa. Complementa PRD-010/060, SPEC-011 e ADR-007/008.

## Resultado esperado

Detectar um possível incidente, abrir ou atualizar chamado, investigar, preparar correção, solicitar autorização ao responsável, executar somente o escopo autorizado, validar recuperação, registrar evidências e encerrar conforme política. Se não puder resolver, manter o chamado aberto, informar o impedimento e encaminhar para atendimento humano.

## Jornada

1. Incidente recebe prioridade, owner e evidências; sinais insuficientes ficam em observação.
2. Agente read-only investiga e propõe plano versionado, sem modificar produção.
3. Plano contém alvo exato, ação, parâmetros, risco, impacto esperado, custo, janela, validação e contingência.
4. Responsável recebe solicitação por Teams, WhatsApp ou ITSM e abre aprovação corporativa autenticada.
5. Backend verifica identidade, autoridade, segregação de funções e validade da decisão.
6. Executor revalida condições e aplica apenas o plano aprovado.
7. Verificador independente confirma saúde, integridade/freshness e downstream.
8. Timeline e chamado recebem resultados. Encerramento automático depende de política; P1 pode exigir aceite humano.
9. Impedimento, rejeição, falha ou resultado incerto gera comunicação e handoff com contexto.

## Requisitos funcionais

| ID | Requisito | Aceite |
|---|---|---|
| REM-01 | Preparar sem alterar | Investigação não possui credencial de escrita. |
| REM-02 | Plano explícito | Ausência de alvo, validação ou contingência impede solicitar execução. |
| REM-03 | Aprovação vinculada | Decisão referencia hash e versão imutável do plano. |
| REM-04 | Autorização real | Resposta livre “sim” não concede autorização. |
| REM-05 | Revalidação | Alteração relevante do alvo invalida aprovação. |
| REM-06 | Execução restrita | Executor não executa comando arbitrário gerado por LLM. |
| REM-07 | Recuperação comprovada | Exit code zero não permite fechamento sozinho. |
| REM-08 | Comunicação de falha | Motivo, ações realizadas, estado e próximo responsável são registrados. |
| REM-09 | Fechamento consistente | ITSM indisponível gera sync pending, não falsa confirmação. |
| REM-10 | Revogação | Antes do início, aprovação revogada impede execução. |

## Classes de ação

- Reexecução: somente após avaliar idempotência e risco de duplicar efeitos.
- Rollback de deployment: requer artefato conhecido e compatibilidade de dados/schema.
- Ajuste de configuração: valores exatos e limites aprovados, nunca liberdade genérica.
- Correção de código: criar PR para revisão e CI; aprovação de remediação não contorna branch protection.
- Backfill/reprocessamento: delimitar partições, janela, volume, orçamento e consumidores.
- Alterações destrutivas/irreversíveis: fora do fluxo automático padrão; análise e autorização específicas.

## Caminhos excepcionais

Rejeitado/expirado: não executar. Sem owner/aprovador elegível: escalar. Mudança de escopo: nova aprovação. Falha parcial: parar e avaliar contingência. Resultado desconhecido: reconciliar antes de tentar novamente. Rollback falhou: incidente permanece ativo e recebe escalonamento urgente. Sem permissão: reportar; nunca ampliar credenciais automaticamente.

## Métricas

Tempo até aprovação; aprovação/rejeição; sucesso validado; rollback; falha de rollback; tempo de handoff; redução de MTTR; reabertura em 24h/7d; ações sem autorização (alvo zero); encerramentos indevidos (alvo zero). Metas de latência e cadência dependem do SLA do serviço.

## Rollout

Shadow mode → preparação L1 → execução L2 aprovada por ação em sandbox → piloto limitado em produção → expansão por tipo de runbook. Não habilitar L3 globalmente como consequência desta solicitação.
