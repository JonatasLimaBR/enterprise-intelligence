#!/usr/bin/env bash
# Devolve a demo ao estado congelado. Restaura em segundos, sem reprocessar o ciclo.
set -euo pipefail

PROFILE="${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
CATALOG="${CATALOG:-workspace}"
OPS="${CATALOG}.eict_ops"
SNAP="${CATALOG}.eict_demo_snapshot"
TABLES=(incidents incident_timeline evidence hypotheses hypothesis_reviews narratives run_cost)
DRY_RUN=false

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

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

require_snapshot() {
  if [[ -z "$(scalar "SELECT count(*) AS n FROM ${SNAP}.snapshot_meta")" ]]; then
    echo "snapshot ausente em ${SNAP}." >&2
    echo "rode primeiro: PROFILE=${PROFILE} ./snapshot_demo.sh (com a demo no estado desejado)" >&2
    exit 1
  fi
}

assert_schemas_match() {
  local list divergentes
  list="$(printf "'%s'," "${TABLES[@]}")"
  list="${list%,}"
  divergentes="$(sql "
    SELECT table_name, column_name FROM ${CATALOG}.information_schema.columns
     WHERE table_schema = 'eict_ops' AND table_name IN (${list})
    EXCEPT
    SELECT table_name, column_name FROM ${CATALOG}.information_schema.columns
     WHERE table_schema = 'eict_demo_snapshot' AND table_name IN (${list})" |
    python -c 'import sys, json
rows = json.load(sys.stdin)
print(", ".join(row["table_name"] + "." + row["column_name"] for row in rows))' 2>/dev/null)"
  if [[ -n "$divergentes" ]]; then
    echo "o schema mudou desde o snapshot: ${divergentes}" >&2
    echo "refaça o snapshot: PROFILE=${PROFILE} ./snapshot_demo.sh" >&2
    exit 2
  fi
}

main() {
  local started=$SECONDS
  require_snapshot
  assert_schemas_match

  if [[ "$DRY_RUN" == true ]]; then
    echo "dry-run: snapshot presente e schemas compatíveis; nada foi alterado"
    return
  fi

  for table in "${TABLES[@]}"; do
    sql "CREATE OR REPLACE TABLE ${OPS}.${table} AS SELECT * FROM ${SNAP}.${table}" > /dev/null &
  done
  wait

  local meta produced detected incident
  meta="$(sql "SELECT incident_id, max(produced_at) AS produced_at,
                      max(incident_detected_at) AS detected_at
               FROM ${SNAP}.snapshot_meta GROUP BY incident_id LIMIT 1")"
  incident="$(python -c 'import sys, json; print(json.loads(sys.argv[1])[0]["incident_id"])' "$meta" 2>/dev/null)"
  produced="$(python -c 'import sys, json; print(json.loads(sys.argv[1])[0]["produced_at"])' "$meta" 2>/dev/null)"
  detected="$(python -c 'import sys, json; print(json.loads(sys.argv[1])[0]["detected_at"])' "$meta" 2>/dev/null)"

  echo "estado restaurado em $((SECONDS - started))s"
  echo "incidente ${incident} detectado por execução real em ${detected}"
  echo "snapshot congelado em ${produced}"
}

main "$@"
