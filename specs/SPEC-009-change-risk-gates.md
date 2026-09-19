# SPEC-009 — Change Risk e Gates

## Fluxo

1. receber PR/change;
2. mapear arquivos e componentes para assets;
3. calcular blast radius;
4. agregar scans/testes/contratos;
5. avaliar provenance e obrigações;
6. produzir score explicável;
7. aplicar policy;
8. registrar decisão/override;
9. acompanhar deployment e janela pós-mudança.

## Gates padrão

| Condição | Decisão padrão |
|---|---|
| Secret verificado | Bloquear e rotacionar. |
| CVE crítica explorável em produção | Bloquear, salvo exceção formal. |
| Data contract incompatível | Aprovação de owners e plano de migração. |
| High blast radius + rollback ausente | Bloquear. |
| Alto risco | Aprovação dupla + canary. |
| Código IA verificado | Rodar suite obrigatória; não bloquear só pela origem. |

## Override

Motivo, approver, escopo, compensating controls, expiration e ticket. Overrides vencidos reabrem finding.

## Feedback

Change success/failure atualiza calibração, preservando explicação e evitando punição automática a autor/equipe.

