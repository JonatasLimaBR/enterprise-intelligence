#!/usr/bin/env bash
# Extrai da plataforma os fatos citados no roteiro, no deck e no one-pager.
# Cada fato carrega a própria origem: nada entra nos artefatos sem fonte.
set -euo pipefail

PROFILE="${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
CATALOG="${CATALOG:-workspace}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="${OUTPUT:-${HERE}/numbers.json}"
CHECK_ONLY=false

usage() {
  cat <<'TXT'
uso: PROFILE=<profile> ./collect_numbers.sh [--check]

  --check   não grava; compara numbers.json com a plataforma e falha se divergir
TXT
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; usage >&2; exit 2 ;;
  esac
done

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

main() {
  local ops="${CATALOG}.eict_ops"
  local gold="${CATALOG}.eict_gold"
  local mode=write
  [[ "$CHECK_ONLY" == true ]] && mode=check

  local incident hypothesis cost profile runs
  incident="$(sql "
    SELECT incident_id, state, severity, first_run_id, last_run_id,
           size(affected_assets) AS affected_assets, size(ticket_refs) AS tickets
    FROM ${ops}.incidents ORDER BY detected_at LIMIT 1")"
  hypothesis="$(sql "
    SELECT code, rank, round(confidence, 2) AS confidence,
           size(supporting) AS supporting, size(contradicting) AS contradicting,
           size(missing) AS missing
    FROM ${ops}.hypotheses ORDER BY rank")"
  cost="$(sql "
    SELECT status, round(incremental_cost_usd, 4) AS incremental_cost_usd,
           round(list_cost_usd, 4) AS list_cost_usd
    FROM ${ops}.run_cost ORDER BY updated_at DESC LIMIT 1")"
  profile="$(sql "
    SELECT left_rows, max_key_rows, median_key_rows, round(skew_ratio, 0) AS skew_ratio,
           round(top_key_share, 2) AS top_key_share, hot_key, key
    FROM ${gold}.run_features WHERE skew_ratio IS NOT NULL ORDER BY end_time DESC LIMIT 1")"
  runs="$(sql "
    SELECT result_state, round(duration_s, 0) AS duration_s, git_sha, end_time
    FROM ${gold}.run_features ORDER BY end_time")"

  INCIDENT="$incident" HYPOTHESIS="$hypothesis" COST="$cost" PROFILE_JSON="$profile" \
  RUNS="$runs" CATALOG="$CATALOG" OUTPUT="$OUTPUT" MODE="$mode" PYTHONIOENCODING=utf-8 \
    python "${HERE}/build_numbers.py"
}

main "$@"
