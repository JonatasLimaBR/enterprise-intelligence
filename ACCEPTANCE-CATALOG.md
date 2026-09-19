# Catálogo de Aceite End-to-End

## A21 — Monitoramento de todas as ações

Given ações humanas, de agente e integração no mesmo incidente; then central mostra origem/ator/estado e correlação, sem contar steps como execuções ou entrega de mensagem como resolução. Filtros e totais conciliam com ledger.

## A22 — Traces Langfuse com privacidade

Given interação com retrieval, modelo e tool; then trace liga versões, uso, erro e evidências ao incidente. Conteúdo sensível sintético é redigido antes da exportação; consulta por outro tenant é negada, inclusive em deep links.

## A23 — Observabilidade indisponível

Given exporter Langfuse falha; then painel mostra lag/drops e operação segue com ledger íntegro. Se auditoria obrigatória falha, novas escritas privilegiadas são bloqueadas.

## A24 — Administração versionada

Given administrador edita policy; then validação, diff, impacto, revisão aplicável e audit antecedem publicação. Conflito de versão não sobrescreve alteração concorrente e admin não aprova a própria mudança crítica.

## A25 — Dashboards autorizados

Given acesso revogado; then listagem, busca, cache, agregados, SSE e export respeitam a nova decisão. Campos indisponíveis aparecem como desconhecidos, não zero.

## A18 — Remediação aprovada e fechamento

Given plano imutável e aprovação válida; when executor conclui e verificador comprova recuperação durante a janela; then evidências entram na timeline e o ticket fecha somente após gates e confirmação do ITSM.

## A19 — Impossibilidade de corrigir

Given ausência de permissão, pré-condição inválida ou falha de execução; then nenhuma ampliação automática de privilégio ocorre, a tentativa para/reconcilia, rollback só ocorre se seguro/autorizado, e owner recebe motivo e handoff; incidente continua aberto.

## A20 — Aprovação obsoleta ou duplicada

Given decisão expirada/revogada ou plano alterado; then bloquear execução e pedir nova autorização. Callback duplicado é idempotente; timeout com efeito desconhecido não dispara nova correção sem reconciliação.

## A01 — Spark skew após change

Given run atual 171% mais lento e commit com novo join; when eventos e métricas são ingeridos; then incidente único é aberto, skew/spill são fatos, commit é change correlacionado, hipótese não é marcada confirmada, impacto/SLA aparecem e recomendações citam evidências.

## A02 — Upstream sem dados

Given gold atrasado e compute saudável; then causa técnica primária aponta para upstream sem freshness, evitando recomendação de scale-up.

## A03 — Job verde, dado ruim

Given execução concluída e regra de qualidade crítica violada; then status técnico é success, data status é failed, downstream/owner são notificados conforme contrato.

## A04 — Repetição

Given múltiplos incidentes semelhantes; then problem candidate mostra frequência, impacto acumulado, assinatura e ação permanente.

## A05 — CVE transversal

Given package vulnerável em imagem; then supply chain graph identifica deployments, aplicações, pipelines/agentes e processos; prioridade considera reachability/exposição.

## A06 — Código IA sem provenance

Given estilo aparentemente gerado; then sistema mantém `UNKNOWN`, pode exibir sinal não conclusivo restrito e não bloqueia/pune por origem.

## A07 — Código IA com attestation

Given provenance verificada; then política exige scans/testes aplicáveis, e decisão depende dos resultados, não da origem isolada.

## A08 — Prompt injection via RAG

Given documento pede ação privilegiada; then conteúdo não altera policy, tool call é negada e auditada.

## A09 — ITSM fora

Given incidente P1 e API ITSM indisponível; then incidente permanece operacional internamente, sync entra em retry/DLQ e alerta de integração aparece.

## A10 — Score auditável

Given health 73; then usuário consegue decompor pesos, métricas, freshness, missing values, overrides e policy version.

## A11 — Remediação idempotente

Given action retry; then idempotency key impede execução duplicada e resultado é consistente.

## A12 — Encerramento seguro

Given pipeline recuperado mas freshness inválida; then incidente não fecha automaticamente até validação ou exceção aprovada.

## A13 — Chamado automático classificado

Given incidente acima do limite de confiança/impacto; then um único ticket é criado com prioridade explicável, owner, SLA, impacto, evidências e link, mantendo sincronização bidirecional.

## A14 — Pergunta do gestor pelo Teams/WhatsApp

Given gestor autenticado pergunta o status; then agente aplica autorização e responde com estado atual, impacto, SLA, fatos, hipótese rotulada, owner e próximo passo. Informação não autorizada é omitida e registrada.

## A15 — Savings realizada e reconciliada

Given oportunidade FinOps implementada; then sistema normaliza baseline por volume/preço/câmbio, desconta custos induzidos, evita dupla contagem, verifica guardrails e classifica benefício como realizado somente após a janela de medição.

## A16 — Token spike e loop de agente

Given agente repete tools e eleva tokens/custo; then Unity Gateway/EICT aplica limites configurados, registra invocations e policy decisions, interrompe conforme policy, cria finding/incidente e mostra tokens desperdiçados e contexto causal.

## A17 — Payload governado

Given inference tables habilitadas; then requests/responses permanecem protegidos por Unity Catalog, retenção e classificação; a EICT usa referências/redação e não duplica conteúdo sensível sem aprovação.
