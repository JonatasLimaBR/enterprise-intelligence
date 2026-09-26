#!/usr/bin/env bash
# Prepara a apresentação: liga o warehouse e o App e restaura o estado congelado da demo.
# Ao terminar a apresentação, rode stop_demo.sh — ligados, eles consomem cota.
set -euo pipefail

PROFILE="${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
WAREHOUSE="${WAREHOUSE_ID:?defina WAREHOUSE_ID}"
APP="${APP_NAME:-eict-console-dev}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "ligando o warehouse ${WAREHOUSE}"
databricks warehouses start "$WAREHOUSE" --profile "$PROFILE" > /dev/null
echo "ligando o App ${APP}"
databricks apps start "$APP" --profile "$PROFILE" > /dev/null
echo "restaurando o estado congelado da demo"
PROFILE="$PROFILE" "${HERE}/reset_demo.sh"
echo "pronto. Ao terminar: PROFILE=${PROFILE} WAREHOUSE_ID=${WAREHOUSE} ${HERE}/stop_demo.sh"
