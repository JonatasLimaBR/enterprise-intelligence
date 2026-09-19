# PRD-100 — Portal de operação, visualização e ações

## Status e escopo
Especificação para implementação; não representa um portal publicado. Abrange todos os domínios definidos no kit. Catálogo de rotas e telas em ux/SCREEN-CATALOG.md; definições métricas em specs/SPEC-017-dashboard-metrics.md.

## Objetivo
Dar ao gestor visão empresarial e ao operador contexto para investigar, acompanhar aprovações e executar fluxos governados. Toda ação humana, de agente ou integração precisa ser localizável pelo chamado, alvo, responsável, período e resultado.

## Personas e jornadas
- Gestor: abrir visão executiva → risco → processo → incidente → resultado.
- Operador: fila → evidências → plano → autorização → execução → verificação → fechamento.
- Aprovador: pendências → escopo/risco/diff → aprovar ou rejeitar → acompanhar resultado.
- Engenheiro IA: custo/erro → agente → trace → tool/retrieval/modelo → avaliação → melhoria.
- FinOps: orçamento → driver → oportunidade → iniciativa → economia validada.
- Auditor: decisão → identidade → plano aprovado → efeito → evidências permissionadas.

## Requisitos de produto
| ID | Requisito | Aceite observável |
|---|---|---|
| VIS-01 | Visão executiva por organização/domínio | Score decomposto, freshness e riscos críticos visíveis. |
| VIS-02 | Central de todas as ações | Inclui humanos, agentes, tools, conectores e notificações sem misturar sucesso de entrega com resolução. |
| VIS-03 | Detalhe de ação | Plano, aprovação, execução, validação, rollback e ITSM conectados. |
| VIS-04 | Navegação contextual | Incidente abre ação; ação abre trace; trace retorna ao incidente sem perder filtros. |
| VIS-05 | Filtros globais | Tenant autorizado, ambiente, período, fuso, domínio, owner e criticidade. |
| VIS-06 | Monitoramento atualizado | Mostra lag real e estado reconectando/desatualizado; nunca promete realtime com fonte atrasada. |
| VIS-07 | Exportação permissionada | Mesmos filtros/ACLs do backend, snapshot e auditoria. |
| VIS-08 | Busca global | Resultado respeita tenant e sensibilidade, inclusive snippets. |
| VIS-09 | Personalização | Views salvas com escopo pessoal/equipe; compartilhamento não amplia permissões. |
| VIS-10 | Centro de comunicação | Entrega, erro, destinatário autorizado e canal; não expõe conteúdo sensível desnecessário. |

## Central de ações
Tabela com action_id, tipo, origem, incidente, alvo, ambiente, solicitante, executor, aprovador, risco, estado, idade, duração, custo estimado/real, resultado de validação e sync ITSM. Filtros por todos os campos seguros; ordenação estável e paginação no servidor.

Separar: recomendação; ação aguardando aprovação; execução iniciada; ação bloqueada; efeito desconhecido; rollback; recuperação comprovada; chamado fechado. Uma barra verde de execução não deve ocultar verificação pendente.

Cards: aguardando aprovação, executando, sem heartbeat, bloqueadas, falhas, reconciliando, rollback falhou, recuperadas sem fechamento e sync pendente. Aging por fila, funil por coorte e timeline de eventos completam o dashboard.

## Interações e limites
Portal de visualização é leitura por padrão, mas expõe operações permissionadas a operadores/aprovadores. Não existe botão de retry que ignore SPEC-014. Cancelar significa solicitar parada segura. Reexecutar cria tentativa vinculada e passa pela policy. Download de payload é separado de acesso à métrica.

## Experiência transversal
Português BR, timestamps com fuso explícito, estados textuais além de cor, acessibilidade por teclado, layout responsivo. Desktop para investigação; mobile para consulta e revisão de aprovação com todos os riscos visíveis. Carregamento, vazio real, ausência de integração, acesso negado, erro parcial, dado obsoleto e indisponibilidade são estados distintos.

## Sucesso
Menor tempo para localizar ação/owner; menos aprovações vencidas; redução de ações sem evidência; dashboard conciliado com ledger; ausência de vazamento entre tenants. Metas iniciais: renderização p95 de página de resumo até 3 s com cache; detalhe até 2 s de API; medir sob carga definida no piloto.

