# SPEC-017 — Catálogo de dashboards e métricas

## Regras de cálculo
Usar event time UTC, exibir fuso selecionado. Toda métrica informa janela, fonte, watermark, amostra, filtros, fórmula/versão e confiança. Não calcular sucesso somente sobre execuções que já terminaram sem mostrar pendentes. Contagens por ID único; somar eventos não equivale a somar ações.

## Dashboards
| ID | Público | Conteúdo | Fonte primária | Atualização alvo |
|---|---|---|---|---|
| DASH-01 Executivo | Gestor | Saúde, riscos, SLA, impacto estimado | Read model + grafo | 60 s |
| DASH-02 Ações | Operador | Estado, origem, aging, falhas, bloqueios | Ledger de ações | 5–15 s |
| DASH-03 Aprovações | Aprovador | Pendentes, vencendo, rejeitadas, invalidadas | Approval store | 5–15 s |
| DASH-04 Remediação | SRE | Tentativas, verificação, rollback, reabertura | Execution/verification | 5–15 s |
| DASH-05 Incidentes | Operador | Severidade, MTTA/MTTR, recorrência | Incident + ITSM | 30 s |
| DASH-06 SLA | Owner | Burn rate, ETA, breach, confiança | Métricas/SLO | 60 s |
| DASH-07 DataOps | Engenharia | Jobs, atraso, retries, dependências | Conectores | Watermark da fonte |
| DASH-08 Spark/SQL | Engenharia | Runtime, skew, spill, scan e planos | Spark/query telemetry | Watermark da fonte |
| DASH-09 Qualidade | Steward | Regras, freshness, contratos | Quality results | Por avaliação |
| DASH-10 IA | AI Engineer | Traces, falhas, latência e handoffs | Langfuse + read model | Alvo 60 s após ingestão |
| DASH-11 Tokens | FinOps/IA | Usage, cache, custo/sucesso, orçamento | Usage deduplicado | Alvo 60 s após ingestão |
| DASH-12 Avaliações | AI Owner | Qualidade, amostra, regressões | Scores/datasets | Por experimento |
| DASH-13 Segurança | Security | Findings, exposure, tool denials | Scanners/policy ledger | 60 s após ingestão |
| DASH-14 Código | Engenharia | Gates, risco, cobertura, provenance | Git/CI/scanners | Por evento |
| DASH-15 FinOps | Gestor/FinOps | Alocação, forecast e savings realizadas | Billing/allocations | Conforme faturamento |
| DASH-16 Processos | Business Owner | Etapas, gargalos e impacto | Eventos de negócio | Conforme fonte |
| DASH-17 Conhecimento | Sustentação | Recorrência, runbooks eficazes | Problem/knowledge | 15 min |
| DASH-18 Plataforma | PlatformAdmin | Filas, DLQ, connector lag, exporter | OTel + health | 15–30 s |
| DASH-19 Comunicação | Operador | Enviadas, entregues, falhas e sync | Outbox/adapters | 30 s |
| DASH-20 Governança | Auditor | Owners, revisões, acessos, exceções | Catalog/audit/policies | 15 min |

Cadências são requisitos-alvo, não garantias de fontes assíncronas. Se falta capability ou integração, exibir não conectado/indisponível.

## Definições canônicas
| Métrica | Fórmula/unidade | Exclusões e limites |
|---|---|---|
| Ações em execução | Count distinct execution_id com estado EXECUTING no instante | Não contar step nem trace. |
| Aging de aprovação | agora − submitted_at por pedido pendente | Mostrar mediana, p95 e mais antigo. |
| Taxa de aprovação | pedidos aprovados / pedidos decididos na coorte de submissão | Exibir rejeitados, expirados e pendentes separados. |
| Sucesso de execução | tentativas com steps concluídos / tentativas terminais | Não chamar de resolução. |
| Recuperação validada | tentativas com verdict RECOVERED / tentativas terminais verificáveis | Indicar inconclusivas/sem dados e janela. |
| Fechamento validado | incidentes fechados com verificação exigida / incidentes fechados | Audit obrigatório mesmo sem trace. |
| Rollback rate | tentativas com rollback iniciado / tentativas de remediação iniciadas | Mostrar ainda em execução e causa. |
| Reabertura | incidentes reabertos / fechados elegíveis para janela 24h ou 7d | Coortes recentes sem janela completa não entram. |
| MTTA | acknowledged_at − detected_at | Sem acknowledgement fica pending; não zero. |
| MTTR operacional | recovered_at − detected_at | Fechamento administrativo medido à parte. |
| Tokens/tarefa bem-sucedida | tokens de todas as tentativas da coorte / tarefas com sucesso validado | Custo de falhas aparece; não só contar chamadas bem-sucedidas. |
| Tool success | tools concluídas conforme contrato / chamadas terminadas | Policy denials apresentados separadamente. |
| Handoff completeness | handoffs com campos obrigatórios válidos / handoffs avaliados | Não implica qualidade da resposta. |
| Groundedness | scores pela rubric versionada na amostra avaliada | Não apresentar como “taxa real de alucinação”. |
| Cobertura de trace | operações elegíveis correlacionadas a trace / operações elegíveis no ledger | Ajustar interpretação por sampling e lag. |
| Lag | ingested_at − event_time; watermark por fonte | Não confundir atraso do source com refresh da UI. |

## Drill-down
Cada widget abre lista com os mesmos filtros e IDs usados no cálculo. Exportação replica o snapshot e inclui definição da métrica. Comparação entre períodos usa janelas de igual duração e informa mudanças de política/volume. Percentis devem ser calculados sobre amostras/distribuição adequada, não média de percentis diários.

## Alertas do painel de ações
Aprovação perto de expirar; execução sem heartbeat; resultado desconhecido; rollback falhou; recuperação não comprovada; ITSM sync pendente; notificação falhou. Thresholds e owners vêm de configuração versionada. Alertas deduplicam por entidade/tipo/janela e não disparam nova remediação recursiva.

