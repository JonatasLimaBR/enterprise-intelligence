#!/usr/bin/env bash
# Janela de verificação das features pendentes, dentro da cota da Free Edition.
# A lógica (orçamento, retomada, relatório) está em verify_pending.py; aqui só o ambiente.
#
#   PROFILE=eict WAREHOUSE_ID=<id> ./verify_pending.sh            # começa ou retoma
#   PROFILE=eict WAREHOUSE_ID=<id> ./verify_pending.sh --reset    # descarta o progresso
#
# Opcionais: BUDGET_MINUTES (45), BUDGET_RUNS (8), SLA_WAIT_MIN (8), WORKLOAD_REPO, CATALOG.
set -euo pipefail

: "${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
: "${WAREHOUSE_ID:?defina WAREHOUSE_ID}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-${HERE}/../eict-platform/.venv/Scripts/python}"
[[ -x "$PYTHON" ]] || PYTHON="python"

export PROFILE WAREHOUSE_ID
exec "$PYTHON" "${HERE}/verify_pending.py" "$@"
