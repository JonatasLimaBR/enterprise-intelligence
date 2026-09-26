#!/usr/bin/env bash
# Desliga o App e o warehouse da demo: ligados, consomem cota mesmo sem ninguém usar.
# Já parado não é erro.
set -uo pipefail

PROFILE="${PROFILE:?defina PROFILE com o nome do profile do Databricks CLI}"
WAREHOUSE="${WAREHOUSE_ID:?defina WAREHOUSE_ID}"
APP="${APP_NAME:-eict-console-dev}"

stop() {
  local descricao="$1"
  shift
  if saida=$("$@" --profile "$PROFILE" 2>&1); then
    echo "${descricao}: desligado"
  else
    echo "${descricao}: não desligado (talvez já estivesse parado): ${saida##*$'\n'}"
  fi
}

stop "App ${APP}" databricks apps stop "$APP"
stop "warehouse ${WAREHOUSE}" databricks warehouses stop "$WAREHOUSE"
exit 0
