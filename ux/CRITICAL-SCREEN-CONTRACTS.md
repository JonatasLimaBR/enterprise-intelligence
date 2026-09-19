# Contratos detalhados das telas críticas

## Central de ações — OPS-03
Pergunta: o que está acontecendo e onde agir?
Topo: filtros globais, as_of e indicador de atraso. Primeira faixa: pending approval, executing, blocked, reconciling, failed rollback, recovered/sync pending. Centro: tabela de ações agrupável por incidente, ator, origem e estado. Lateral: detalhe de seleção sem perder filtro. Base: aging por estado e eventos recentes.
Clique em card filtra tabela; clique na ação abre OPS-04. Somente incident/execution IDs únicos entram nos totais respectivos. Itens humanos e de agente possuem rótulo de origem. Notificação entregue não incrementa “incidente resolvido”.
Teste: duas tasks do mesmo plano geram duas linhas de step no detalhe, mas somente uma execução no KPI.

## Revisão de aprovação — OPS-06
Cabeçalho: incidente, alvo, ambiente, prioridade e expiração. Plano: ação, runbook/digest, parâmetros, motivo, evidências, efeitos esperados, custo/teto, janela. Risco: dependentes, pré-condições, rollback/compensação e verificação. Rodapé fixo: Aprovar, Rejeitar, Solicitar revisão.
Botões exigem identidade, autoridade atual e plano/hash. Aprovação não pode ocorrer sem abrir escopo completo no mobile. Se expire/target changed, substituir CTA por solicitar novo plano. Rejeição registra motivo. Não aceitar aprovação por URL GET.

## Execução — OPS-08
Etapas com início/fim, worker, heartbeat e resultado observável. Logs redigidos; evidência por referência. Painel separado para autorização, efeito e recuperação. Botão cancelar exibe “parada solicitada”; não afirmar cancelado até confirmação. Retry desabilitado em RECONCILING.
Checks pós-ação mostram PASS/FAIL/UNKNOWN e validade da medição. Rollback é outra tentativa rastreável no mesmo plano autorizado. Badge do ITSM é independente do status operacional.
Teste: timeout externo mostra efeito desconhecido; não verde nem execução duplicada.

## Workspace de incidente — OPS-11
Abas: resumo; timeline; evidências; hipóteses; changes; impacto; ações/aprovações; comunicação; recuperação; postmortem. Ordenar fatos por event time e indicar chegada tardia. Estado confirmado separado de hipótese.
Fechar habilitado apenas quando policy permite, verificação válida e owner confirma quando exigido. Backend revalida, mesmo que o botão esteja habilitado. Edição concorrente mostra diff.

## Trace explorer e detalhe — OPS-29/30
Lista: trace ID, sessão, release, agente, período, status, duração, uso reportado e custo estimado. Filtros por agente/modelo/falha e IDs EICT autorizados. Detalhe: waterfall, observações, ferramenta, retrieval, gerações, handoffs, tokens e scores.
Separar duração ponta a ponta da soma dos spans: paralelismo impede equivalência. Campos não reportados são N/A. Payload só com permissão específica; cópia/export redigidos. Deep link ao Langfuse exige autorização efetiva no destino.
Não mostrar cadeia interna de pensamento; mostrar plano objetivo, fontes e resultados.

## Langfuse admin — ADM-21/22
Wizard: tipo de deployment → destino permitido → projeto/ambiente → secret ref → fronteira de isolamento → metadata/payload policy → sampling/retention → trace sintético → validação → publicar.
Não enviar prompt real durante teste. Resultado informa export recebido, redaction verificada, lag e SDK/API compatibility. Campos de segredo não têm botão revelar. Erro de credencial mostra código seguro e procedimento de rotação.
Publish exige diff e revisão quando amplia coleta ou acesso. “Connection OK” não prova isolamento; verificar usuário restrito e tentativa cross-tenant.

## Portal executivo — OPS-01
Primeiro bloco: processos ameaçados e decisões pendentes. Segundo: saúde por domínio com confiança e cobertura. Terceiro: custos/benefícios com metodologia e janela. Quarto: mudanças, incidentes e ações relevantes.
Gestor pode perguntar no assistente; resposta usa os mesmos filtros e escopos da tela. Filtro do gráfico não constitui autorização. Impacto estimado nunca é apresentado como prejuízo confirmado.

## Policies admin — ADM-15/16
Editor estruturado para condição, efeito, owner, escopo e vigência. Simulação sobre fixtures mostra allowed/denied/approval e diferença entre versões. Revisão identifica approver elegível. Publicação gera audit e evento para invalidar caches/aprovações afetadas. Rollback de policy também é mudança versionada.

## Acessibilidade e aceite comuns
Foco visível, nomes acessíveis, tabela navegável, status em texto, anúncio de atualização sem roubar foco, pausar refresh para investigação, contraste e zoom. Datas absolutas junto de “há 5 min”. Preservar filtros em URLs sem incluir conteúdo sensível. Testar sessão expirada durante aprovação: recuperar contexto, exigir autenticação e não reenviar comando automaticamente.

