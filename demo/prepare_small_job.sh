#!/usr/bin/env bash
# Prepara o gatilho ao vivo: tabela reduzida, baseline do job pequeno e o primeiro
# incidente dele. Roda uma vez; depois a apresentação usa só trigger_recorrencia.sh.
set -euo pipefail

PROFILE="${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
CATALOG="${CATALOG:-workspace}"
SCHEMA="${SCHEMA:-eict_workload}"
FRACTION="${FRACTION:-0.10}"
BASELINE_RUNS="${BASELINE_RUNS:-5}"
WAREHOUSE="${WAREHOUSE_ID:?defina WAREHOUSE_ID}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKLOAD="${ROOT}/eict-demo-workload"
MEASURE_ONLY=false

[[ "${1:-}" == "--measure-only" ]] && MEASURE_ONLY=true

sql() {
  databricks experimental aitools tools query "$1" --profile "$PROFILE" -o json > /dev/null 2>&1
}

run_job() {
  local heavy="$1" started elapsed
  started=$SECONDS
  databricks bundle run sales_daily_small -t dev --profile "$PROFILE" \
    --var="warehouse_id=${WAREHOUSE}" --params "heavy=${heavy}" > /dev/null 2>&1
  elapsed=$((SECONDS - started))
  echo "$elapsed"
}

create_small_table() {
  echo "criando ${CATALOG}.${SCHEMA}.orders_small (~${FRACTION} de orders, mesmo skew)"
  sql "CREATE OR REPLACE TABLE ${CATALOG}.${SCHEMA}.orders_small AS
       SELECT * FROM ${CATALOG}.${SCHEMA}.orders WHERE rand(42) < ${FRACTION}"
}

measure() {
  echo "medindo versão leve..."
  local light heavy factor
  light="$(run_job false)"
  echo "  leve:   ${light}s"
  echo "medindo versão pesada..."
  heavy="$(run_job true)"
  echo "  pesada: ${heavy}s"
  factor="$(python -c "print(round(${heavy} / max(${light}, 1), 2))")"
  echo "  fator:  ${factor}x"
  python -c "
import sys
factor = ${factor}
if factor < 1.5:
    print('fator abaixo de 1.5: aumente FRACTION ou RECENT_ORDERS antes de formar o baseline')
    sys.exit(1)
if ${heavy} > 420:
    print('run pesado acima de 7 min: reduza FRACTION')
    sys.exit(1)
print('A-001 validada: o gatilho cabe na apresentação')
"
}

main() {
  cd "$WORKLOAD"
  databricks bundle deploy -t dev --profile "$PROFILE" --var="warehouse_id=${WAREHOUSE}" > /dev/null
  create_small_table
  measure

  if [[ "$MEASURE_ONLY" == true ]]; then
    echo "medição concluída; rode sem --measure-only para formar o baseline"
    return
  fi

  echo "formando baseline (${BASELINE_RUNS} runs leves)"
  for index in $(seq 1 "$BASELINE_RUNS"); do
    echo "  run ${index}/${BASELINE_RUNS}: $(run_job false)s"
  done

  echo "primeiro run pesado (abre o incidente do job pequeno)"
  run_job true > /dev/null

  echo "rodando o ciclo da plataforma"
  cd "${ROOT}/eict-platform"
  databricks bundle run eict_cycle -t dev --profile "$PROFILE" \
    --var="warehouse_id=${WAREHOUSE},github_repo=${GITHUB_REPO:-}" > /dev/null

  echo "pronto: use trigger_recorrencia.sh durante a apresentação"
}

main "$@"
