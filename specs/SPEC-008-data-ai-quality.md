# SPEC-008 — Regras de Qualidade de Dados e IA

## Regra de dados

Campos: `rule_id`, `asset`, `dimension`, `expression`, `threshold`, `window`, `severity`, `owner`, `action`, `sampling`, `version`.

Tipos: null, uniqueness, range, regex, referential, freshness, volume, distribution, schema, reconciliation e custom SQL.

## Execução

Rules podem rodar in-engine, federadas ou por amostra. Resultado registra numerador, denominador, limites, amostra, query hash e evidence ref. Falha do engine não é violação de dado; é status `evaluation_error`.

## Avaliação de GenAI

Dataset versionado com input, expected behavior, rubric, risk category e protected fields. Métricas automáticas e humanas são separadas. LLM-as-judge registra modelo, prompt, temperatura e calibration set.

## Gates

- breaking schema: block/approval;
- freshness crítica: downstream hold opcional;
- groundedness abaixo do limite: canary stop ou fallback;
- safety failure: bloqueio;
- drift: review/retrain workflow, não retreino automático cego.

