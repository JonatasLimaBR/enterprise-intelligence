#!/usr/bin/env bash
# Congela o estado operacional atual para que a demo possa ser restaurada em segundos.
# O snapshot guarda saída real de uma execução verdadeira: nada aqui é fabricado.
set -euo pipefail

PROFILE="${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
CATALOG="${CATALOG:-workspace}"
OPS="${CATALOG}.eict_ops"
SNAP="${CATALOG}.eict_demo_snapshot"
TABLES=(incidents incident_timeline evidence hypotheses hypothesis_reviews narratives run_cost)

sql() {
  databricks experimental aitools tools query "$1" --profile "$PROFILE" -o json 2>/dev/null |
    python -c 'import sys, json
text = sys.stdin.read()
start = text.find("[")
try:
    rows = json.loads(text[start:]) if start >= 0 else []
except ValueError:
    rows = []
print(json.dumps(rows))' 2>/dev/null
}

scalar() {
  sql "$1" | python -c 'import sys, json; rows = json.load(sys.stdin); print(rows[0][list(rows[0])[0]] if rows else "")' 2>/dev/null
}

require_incident() {
  local count
  count="$(scalar "SELECT count(*) AS n FROM ${OPS}.incidents")"
  if [[ "$count" == "0" || -z "$count" ]]; then
    echo "não há incidente em ${OPS}.incidents; rode o ciclo antes de congelar" >&2
    exit 1
  fi
  echo "incidentes a congelar: ${count}"
}

main() {
  require_incident
  sql "CREATE SCHEMA IF NOT EXISTS ${SNAP}" > /dev/null

  for table in "${TABLES[@]}"; do
    sql "CREATE OR REPLACE TABLE ${SNAP}.${table} AS SELECT * FROM ${OPS}.${table}" > /dev/null
    echo "  congelado: ${table} ($(scalar "SELECT count(*) AS n FROM ${SNAP}.${table}") linhas)"
  done

  sql "CREATE OR REPLACE TABLE ${SNAP}.snapshot_meta AS
       SELECT current_timestamp() AS produced_at,
              (SELECT incident_id FROM ${OPS}.incidents ORDER BY detected_at LIMIT 1) AS incident_id,
              (SELECT max(detected_at) FROM ${OPS}.incidents) AS incident_detected_at" > /dev/null

  echo "snapshot pronto em ${SNAP}"
  echo "restaure a qualquer momento com: PROFILE=${PROFILE} ./reset_demo.sh"
}

main "$@"
