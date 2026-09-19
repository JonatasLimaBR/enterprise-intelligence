# PRD-110 — Portal administrativo

## Objetivo
Configurar operação, identidades, integrações, agentes, observabilidade e políticas com versionamento, validação e trilha. Administração da plataforma não concede automaticamente leitura de payload sensível nem autoridade para aprovar a própria correção.

## Escopo
Tenants/unidades/domínios; usuários/grupos/service principals; roles e escopos; SSO; conexões e credenciais referenciadas; ITSM; Teams/WhatsApp; Langfuse; Unity Gateway; agentes/tools; policies; budgets; contratos; semântica; SLAs; runbooks; alertas; retenção; auditoria; dashboards; manutenção; feature flags e saúde interna.

## Requisitos
| ID | Capacidade | Aceite |
|---|---|---|
| ADM-01 | Onboarding de fonte | Teste read-only, capabilities, owner, scope, periodicidade e estado. |
| ADM-02 | Gestão de acesso | Prévia de acesso efetivo, revisão e expiração; sem autoelevação. |
| ADM-03 | Segredos | Somente referência ao secret manager; nunca revelar valor salvo. |
| ADM-04 | Policy lifecycle | Draft, validar, simular, revisar, publicar, retirar; histórico e diff. |
| ADM-05 | Langfuse | Mapear projeto/ambiente/tenant, retenção e redaction; teste sem payload real. |
| ADM-06 | Runbooks | Versão, digest, schema de parâmetros, risco, contingência e aprovação. |
| ADM-07 | Notificações | Templates, canais, destinos resolvidos, quiet hours e escalonamento. |
| ADM-08 | Configuração de scoring | Simulação antes/depois sobre fixtures; versão nos resultados. |
| ADM-09 | Operação da plataforma | Filas, DLQ, connectors, coleta, replay governado e kill switch. |
| ADM-10 | Budgets/quotas | Autoridade financeira separada, limites, vigência e simulação de impacto. |
| ADM-11 | Dados sensíveis | Retenção, minimização, eliminação e legal hold conforme processo. |
| ADM-12 | Auditoria administrativa | Quem mudou, quê, antes/depois redigido, motivo, revisão e resultado. |

## Fluxo de publicação de configuração
Formulário → validação de schema → análise de impacto → preview/diff → revisão conforme risco → publicação de versão → acompanhamento → rollback de configuração se compatível.
Alterar limites de autonomia, tools de escrita, budgets críticos, permissões ou retention é mudança material. Policy publicada pode invalidar aprovações ainda não executadas.

## Segurança de administração
Sessões com expiração; step-up para mudanças sensíveis; CSRF quando cookie; permissões no backend; identificadores tenant validados; bloqueio de exclusão de último administrador por rotina comum; sem impersonation silenciosa. Acesso emergencial temporário, auditado, revisado posteriormente e restrito ao escopo necessário.

## Saúde e indisponibilidade
Conector inacessível não aparece como ativo saudável. Mapeamento Langfuse inválido bloqueia exportação desse escopo. Falha de policy store bloqueia execução privilegiada. Falha apenas de analytics não interrompe consulta básica do incidente se store operacional disponível.

## KPIs
Configurações inválidas prevenidas, tempo de onboarding, connectors saudáveis, revisões de acesso vencidas, mudanças com aprovação, drift entre configuração desejada e observada.

