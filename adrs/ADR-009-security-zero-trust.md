# ADR-009 — Zero Trust, workload identity e menor privilégio

- Status: Aceita

## Decisão

Cada connector, agente e action executor usa identidade própria, credencial de curta duração, escopo mínimo e rede restrita. Secrets permanecem em secret manager; nunca entram em prompt, event payload ou log.

## Consequências

Melhor contenção de blast radius; requer maturidade IAM e rotação automatizada.

