# UX e Arquitetura de Informação

## Expansão do escopo de interface

Navegação organizada em /ops (operação/visualização) e /admin (administração), com backend permissionado comum. O catálogo completo é `SCREEN-CATALOG.md`; contratos detalhados em `CRITICAL-SCREEN-CONTRACTS.md`; métricas em `../specs/SPEC-017-dashboard-metrics.md`. A lista resumida abaixo é agrupamento de domínios, não limite de telas.

## Navegação

1. Command Center
2. Incidents
3. Risks
4. Services & Assets
5. Data & Quality
6. AI & Agents
7. Code & Changes
8. Security
9. Costs
10. Processes
11. Knowledge
12. Governance/Admin

## Command Center

Enterprise Health, critical incidents, predicted breaches, top risks, changes, business impact, owner gaps e ação prioritária. Evitar wall of charts: responder “o que precisa ser tratado agora?”.

## Tela de incidente

Cabeçalho com severity/state/SLA/owner; impacto; timeline; evidence; RCA hypotheses; affected graph; recent changes; recommendations/actions; collaboration; related incidents/problems.

## Tela de change/PR

Risk score, fatores, files/assets, blast radius, scans, tests, provenance, gates, approvals, deployment status e post-change health.

## Tela AI/Agent

Health, versions, quality, cost, latency, tools, handoffs, safety, evaluations, data dependencies e recent changes.

## UX de confiança

Badges visuais para Fact, Inference, Recommendation e Policy Decision. Mostrar confiança e missing evidence. Usuário pode contestar, corrigir owner/relação e registrar conclusão.

## Acessibilidade

WCAG 2.2 AA, navegação por teclado, contraste, texto alternativo e não depender apenas de cor para severidade.
