#!/usr/bin/env bash
set -euo pipefail

PROFILE="${PROFILE:-eict}"
TARGET="${TARGET:-dev}"
BASELINE_RUNS="${BASELINE_RUNS:-7}"
REGRESSION_RUNS="${REGRESSION_RUNS:-2}"
BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { printf '\n=== %s\n' "$1"; }

require_clean_git() {
  if [[ -n "$(git -C "$BUNDLE_DIR" status --porcelain)" ]]; then
    echo "workspace git sujo: faça commit antes (o SHA é a evidência de change)" >&2
    exit 1
  fi
}

deploy() {
  databricks bundle deploy -t "$TARGET" --profile "$PROFILE"
}

run_job() {
  databricks bundle run "$1" -t "$TARGET" --profile "$PROFILE"
}

measure_last_run() {
  databricks bundle run sales_daily -t "$TARGET" --profile "$PROFILE" -o json |
    python -c "import json,sys; run=json.load(sys.stdin); print(int((run['end_time']-run['start_time'])/1000))"
}

main() {
  require_clean_git
  cd "$BUNDLE_DIR"

  log "deploy do commit A"
  deploy

  log "gerando dataset sintético"
  run_job generate_data

  log "medindo um run da versão A"
  baseline_seconds="$(measure_last_run)"
  echo "versão A: ${baseline_seconds}s"

  log "formando baseline (${BASELINE_RUNS} runs)"
  for _ in $(seq 2 "$BASELINE_RUNS"); do
    run_job sales_daily
  done

  log "aplicando commit B (join de segmentos + Window na chave quente)"
  cp scenario/sales_daily_v2.py src/sales_daily.py
  git add src/sales_daily.py
  git commit -m "feat: add customer segment join and per-customer ranking"
  deploy

  log "medindo a versão B"
  regression_seconds="$(measure_last_run)"
  echo "versão B: ${regression_seconds}s"

  python - "$baseline_seconds" "$regression_seconds" <<'PY'
import sys
baseline, regression = int(sys.argv[1]), int(sys.argv[2])
factor = regression / max(baseline, 1)
print(f"fator de regressão: {factor:.2f}x")
if factor < 1.5:
    print("A-009 NÃO validada: aumente --scale ou --hot-share antes de seguir", file=sys.stderr)
    sys.exit(1)
print("A-009 validada")
PY

  log "runs lentos adicionais (idempotência do incidente)"
  for _ in $(seq 2 "$REGRESSION_RUNS"); do
    run_job sales_daily
  done

  log "cenário concluído — rode o eict_cycle da plataforma para correlacionar"
}

main "$@"
