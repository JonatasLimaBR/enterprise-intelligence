#!/usr/bin/env bash
# Dispara, durante a apresentação, uma execução lenta de verdade no job pequeno.
# Ela entra como recorrência no incidente daquele job — não cria incidente novo.
set -euo pipefail

PROFILE="${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
WAREHOUSE="${WAREHOUSE_ID:?defina WAREHOUSE_ID}"
GITHUB_REPO="${GITHUB_REPO:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_CYCLE=false

[[ "${1:-}" == "--no-cycle" ]] && SKIP_CYCLE=true

main() {
  local started=$SECONDS

  echo "disparando execução lenta no job pequeno (leva alguns minutos)"
  cd "${ROOT}/eict-demo-workload"
  databricks bundle run sales_daily_small -t dev --profile "$PROFILE" \
    --var="warehouse_id=${WAREHOUSE}" --params "heavy=true" | tail -2

  if [[ "$SKIP_CYCLE" == true ]]; then
    echo "execução concluída em $((SECONDS - started))s; ciclo não disparado (--no-cycle)"
    return
  fi

  echo "rodando o ciclo da plataforma para correlacionar"
  cd "${ROOT}/eict-platform"
  databricks bundle run eict_cycle -t dev --profile "$PROFILE" \
    --var="warehouse_id=${WAREHOUSE},github_repo=${GITHUB_REPO}" | tail -2

  echo "pronto em $((SECONDS - started))s — atualize o console"
  echo "o incidente do job pequeno deve mostrar uma nova entrada de recorrência"
}

main "$@"
