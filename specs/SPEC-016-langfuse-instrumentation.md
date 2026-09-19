# SPEC-016 — Instrumentação Langfuse e correlação operacional

## Limites de responsabilidade
Langfuse: traces IA e avaliações. OpenTelemetry/APM: desempenho de serviços. EICT ledger: autorização/efeitos. Unity Gateway: enforcement onde disponível. Billing: valores faturados. Integrar por IDs, sem pressupor que uma fonte contém todas as outras.

## Mapeamento canônico
| EICT | Destino/convenção |
|---|---|
| Interação de usuário | Trace de uma operação. |
| Conversa Teams/WhatsApp/portal | Session ID pseudônimo e com escopo tenant. |
| Chamada ao modelo | Observation de geração com usage quando reportado. |
| Retrieval/tool/handoff | Observações aninhadas ou spans associados. |
| incident/plan/execution ID | Metadata allowlisted, não atributos de alta cardinalidade em métricas agregadas. |
| Prompt e release | Referências de versão, nunca apenas nome “latest”. |
| Avaliação | Score com rubric, evaluator/version, amostra e evidence refs. |

Base técnica consultada: [modelo Langfuse](https://langfuse.com/docs/observability/data-model). Traces agrupam observações; sessões agrupam interações; a integração usa OpenTelemetry. Exportação é assíncrona; processos curtos precisam de flush antes de sair. Confirmar SDK/API e pin de versão no spike.

## Fluxo instrumentado de referência
1. Receber interação e validar identidade.
2. Abrir trace; registrar apenas metadata permitida.
3. Buscar incidente/evidências com autorização.
4. Registrar retrieval (IDs de fontes, tamanho, latência; conteúdo omitido por padrão).
5. Registrar gerações de modelo e chamadas de tools.
6. Registrar handoff com objetivo resumido e status.
7. Persistir proposta/aprovação no ledger; anotar IDs no trace.
8. Encerrar trace da interação.
9. Aprovação posterior e worker de execução abrem novos traces ligados ao workflow.
10. Verificação e sync ITSM são novas operações correlacionadas.

Não manter span aberto durante horas de espera humana. Trace não armazena raciocínio interno privado do modelo; registrar plano, justificativa objetiva, fontes e resultados observáveis.

## Propagação
Usar traceparent/tracestate conforme integração suportada; propagar IDs de correlação em mensagem interna. Não confiar em tenant/user informados pelo cliente. Contexto de fila validado no consumer. Relação persistida no EICT: tenant_id, workflow_id, event_id, trace_id, observation_id?, request_id?, invocation_id?, project_ref, external_url_ref.

## Tokens e custos
Capturar usage reportado; ausência é desconhecido. Reasoning/cached tokens podem ser subconjuntos, portanto não somar duas vezes. Armazenar input/output/total e breakdown com semântica por provider. Dedup preferencial por provider request/invocation id mais tenant; sem ID confiável, marcar associação incerta.
Custos Langfuse/SDK e Unity Gateway da mesma chamada não são somados. Escolher fonte autoritativa por categoria; reconcile com billing. Custos de judges ficam em categoria evaluation, separados da inferência para o usuário.

## Privacidade e isolamento
Redigir inputs, outputs, erros, tool arguments, URLs e metadata antes do exporter; não confiar apenas em masking na UI. Allowlist de metadata. User/session IDs pseudônimos; tags não incluem CPF, e-mail ou segredo.
Mapear tenant/ambiente a projeto/instância conforme capabilities de isolamento. Filtrar tenant em um projeto compartilhado não impede acesso direto no Langfuse. Se não houver isolamento equivalente, bloquear acesso direto e usar instância/projeto separado ou BFF restrito. Chaves ficam em secret manager no servidor.
Referências: [masking](https://langfuse.com/docs/observability/features/masking), [RBAC](https://langfuse.com/docs/administration/rbac). Features de papéis por projeto dependem de edição/plano; validar antes da contratação/implantação.

## Exportação, sampling e falhas
Fila limitada e criptografada quando persistente; batch, backoff, retry limitado e contador de drops. Overflow não deve consumir memória ilimitada. Coletar lag, queue depth, dropped spans, rejected payloads, exporter errors, quota e última entrega.
Sampling determinístico por trace mantém cadeia coerente. Tentativas de retenção adicional para erros dependem da capacidade do collector escolhido; não prometer captura perfeita. Auditoria de actions não tem sampling.
Langfuse fora: continuar leitura com banner de degradação; exportar depois quando possível. Ledger/auditoria de escrita fora: bloquear nova ação privilegiada. Não esconder perda de telemetria.

## Avaliações e regressões
Rubricas separadas: evidence coverage, correctness validada, groundedness, tool success, policy adherence, handoff completeness. Scores automáticos não confirmam causa raiz nem autorizam correção. Datasets sanitizados, versões e amostras publicadas nos resultados. Julgador calibrado contra revisão humana e testado por segmento. Experimento compara release/prompt/modelo com quality, safety, custo e latência; gate revisado antes de promoção.
Base: [avaliação Langfuse](https://langfuse.com/docs/evaluation/overview).

## Exemplo de evento sintético
```json
{
  "tenant_id": "demo",
  "workflow_id": "wf-demo-001",
  "incident_id": "INC-DEMO-01",
  "execution_id": "exec-demo-01",
  "operation": "verify_recovery",
  "environment": "sandbox",
  "outcome": "inconclusive",
  "reason_code": "FRESHNESS_NOT_RECOVERED",
  "input_tokens": null,
  "usage_status": "not_applicable",
  "payload_policy": "metadata_only"
}
```

## Plano de implementação e aceite
Spike: fixar SDK/API, Cloud ou self-hosted, região, projeto, masking e rede. Instrumentar primeiro chat + uma tool read-only. Depois supervisor/handoffs; depois remediação sandbox; depois avaliações e dashboards.
Fixtures: aprovação negada, tool timeout, prompt injection, retry, fallback, late span, chamada sem tokens, exporter indisponível, payload sensível sintético e acesso cruzado. Conferir ledger completo mesmo com sampling; conferir custo sem duplicação entre fontes. Não usar produção como dataset de teste sem processo aprovado.

