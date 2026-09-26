#!/usr/bin/env bash
# Dispara, durante a apresentação, uma execução lenta de verdade no job pequeno.
# Ela entra como recorrência no incidente daquele job — não cria incidente novo.
set -euo pipefail

PROFILE="${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
WAREHOUSE="${WAREHOUSE_ID:?defina WAREHOUSE_ID}"
GITHUB_REPO="${GITHUB_REPO:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COST_FILE="${ROOT}/demo/.presentation_cost.json"
# Só o que a história da apresentação mostra: qualidade, semântica e dispatch não mudam nada aqui.
PRESENTATION_STAGES="collect,medallion,correlate,narrate"
SKIP_CYCLE=false

[[ "${1:-}" == "--no-cycle" ]] && SKIP_CYCLE=true

# Custo medido (relógio dos comandos, fila incluída) — fonte do fato presentation_compute_min.
record_cost() {
  local segundos="$1" runs="$2"
  printf '{"seconds": %s, "runs": %s, "measured_at": "%s", "stages": "%s"}\n' \
    "$segundos" "$runs" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PRESENTATION_STAGES" > "$COST_FILE"
  echo "consumo medido: $((segundos / 60)) min em ${runs} run(s) — gravado em demo/.presentation_cost.json"
}

main() {
  local started=$SECONDS

  echo "disparando execução lenta no job pequeno (leva alguns minutos)"
  cd "${ROOT}/eict-demo-workload"
  databricks bundle run sales_daily_small -t dev --profile "$PROFILE" \
    --var="warehouse_id=${WAREHOUSE}" --params "heavy=true" | tail -2

  if [[ "$SKIP_CYCLE" == true ]]; then
    echo "execução concluída em $((SECONDS - started))s; ciclo não disparado (--no-cycle)"
    record_cost "$((SECONDS - started))" 1
    return
  fi

  echo "rodando o ciclo da plataforma para correlacionar"
  cd "${ROOT}/eict-platform"
  databricks bundle run eict_cycle -t dev --profile "$PROFILE" \
    --var="warehouse_id=${WAREHOUSE},github_repo=${GITHUB_REPO}" \
    --params "stages=${PRESENTATION_STAGES}" | tail -2
  record_cost "$((SECONDS - started))" 2

  echo "pronto em $((SECONDS - started))s — atualize o console"
  echo "o incidente do job pequeno deve mostrar uma nova entrada de recorrência"
}

main "$@"
