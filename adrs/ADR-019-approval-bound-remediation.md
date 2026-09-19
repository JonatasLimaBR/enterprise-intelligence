# ADR-019 — Aprovação vinculada ao plano e fechamento por evidência

- Status: Aceita para o desenho; implementação pendente.

## Contexto

Uma autorização genérica permite alterações além da intenção humana. Execução bem-sucedida não prova recuperação e retries podem duplicar efeitos.

## Decisão

Vincular aprovação autenticada ao hash de plano imutável com alvos, parâmetros, janela e contingência. Revalidar autoridade, política e estado imediatamente antes da execução. Separar executor de verificador e manter incidente aberto até recuperação comprovada e sincronização ITSM. Aplicar idempotência e reconciliação, sem prometer exactly-once em sistemas externos.

## Alternativas

“Sim” por chat: rejeitada como autorização suficiente. Autorização geral ao agente: rejeitada para este fluxo. Apenas execução manual: permitida como fallback, mas não atende automação aprovada solicitada. Fechamento por exit code: rejeitado por ignorar dados/downstream.

## Consequências

Mais latência e estado operacional, compensados por rastreabilidade, controle de escopo e redução de efeitos duplicados. Alterações relevantes exigem nova aprovação. Ações irreversíveis e branch protections mantêm seus processos próprios.

## Revisão

Revisar após piloto em sandbox e produção limitada, com métricas de recuperação validada, incidentes reabertos, bypass de autorização e falhas de rollback. Não ampliar autonomia automaticamente a partir da taxa de sucesso.
