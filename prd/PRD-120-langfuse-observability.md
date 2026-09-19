# PRD-120 — Observabilidade de IA com Langfuse

## Decisão de produto
Langfuse será a integração de referência para investigação de aplicações LLM. OpenTelemetry/APM cobre APIs, workers, filas e infraestrutura; o ledger EICT preserva ações/aprovações; Unity Gateway aplica governança onde habilitado. Esses papéis são complementares.

## Fontes oficiais consultadas
- [Observabilidade](https://langfuse.com/docs/observability/overview): tracing, tokens, latência e análise de aplicações.
- [Modelo de dados](https://langfuse.com/docs/observability/data-model): observações, traces e sessões.
- [Avaliação](https://langfuse.com/docs/evaluation/overview): avaliações online/offline.
- [Mascaramento](https://langfuse.com/docs/observability/features/masking): proteção antes da ingestão.
- [RBAC](https://langfuse.com/docs/administration/rbac): acesso e restrições por edição.
Consulta em 19/09/2026; confirmar versão/edição no spike. As exigências abaixo são desenho EICT, não promessa de que todo controle é nativo do Langfuse.

## Objetivos
Reconstruir uma interação desde Teams/WhatsApp/portal até retrieval, supervisor, handoffs, chamadas de modelo, tools, políticas e resposta. Associar qualidade, custo e latência ao impacto da operação. Identificar loops, regressões de prompt, falha de tool e falta de evidência.

## Requisitos
| ID | Requisito | Aceite |
|---|---|---|
| OBS-01 | Traces por interação | Correlação com sessão, incidente e release; isolamento por tenant. |
| OBS-02 | Gerações e tools | Modelo, prompt version, tokens, erro, latência e resultado redigido. |
| OBS-03 | Handoff | Origem/destino, objetivo resumido, timeout e estado de retorno. |
| OBS-04 | Aprovação longa | Espera representada como evento do workflow, sem span vivo por dias. |
| OBS-05 | Qualidade | Scores com rubric, avaliador, versão, tamanho da amostra e estado desconhecido. |
| OBS-06 | Feedback | Feedback humano ligado à resposta/trace, não tratado como verdade universal. |
| OBS-07 | Experimentos | Comparação de prompt/modelo com dataset versionado e gates de qualidade. |
| OBS-08 | Custo | Separar inferência estimada, faturamento e custo das avaliações. |
| OBS-09 | Privacidade | Redaction na origem; teste com dado sintético comprova ausência de secret. |
| OBS-10 | Disponibilidade | Falha do exporter visível; auditoria obrigatória continua em ledger independente. |

## Telas
Resumo IA, traces, trace detalhado, sessões, agentes, handoffs, tools/MCP, prompts, avaliações, datasets, experimentos, tokens e saúde de exportação. Portal EICT agrega; deep link ao Langfuse exige permissão equivalente. Sem iframe público e sem chave de projeto no browser.

## Governança e implantação
Escolher Cloud ou self-hosted após revisar residência, capacidade, custo e features necessárias. Self-hosting não elimina custo operacional; não assumir SSO/RBAC avançado grátis. Até validar controle equivalente, usuários restritos consultam dados redigidos apenas pelo backend EICT.

## Aceite do piloto
Uma conversa simulada deve conectar sessão → trace → incidente → plano → aprovação → execução → verificação → fechamento, com timestamps e evidências. Testar erro de tool, fallback, recusa de política, perda do exporter e acesso indevido. Nenhum teste deve executar remediação real em produção.

