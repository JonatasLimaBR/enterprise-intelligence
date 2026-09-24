# Declarações de regime de baseline

Um arquivo `*.yaml` por mudança **planejada** de regime: "a partir deste commit (ou instante),
o runtime deste job tem um novo normal". Regressão inesperada **não** se declara aqui — ela vira
incidente, e o aceite como novo normal é feito no console, com a identidade de quem aceitou.

```yaml
job_id: "65105666981331"
effective_from:          # exatamente um dos dois
  git_sha: 122d695       # vale a partir do 1º run deste commit (abreviado aceito, ≥ 7)
  # at: 2026-09-23T17:00:00Z
owner: plataforma-dados@exemplo.com   # obrigatório
reason: "orders_small recriada com 10% do volume"   # obrigatório
```

Arquivo inválido é recusado inteiro; os demais seguem. O ciclo grava as declarações válidas em
`ops.baseline_regimes`, ao lado dos aceites do console.
