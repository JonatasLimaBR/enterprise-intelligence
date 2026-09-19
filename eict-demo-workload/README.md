# EICT Demo Workload

Job encenado que produz a regressão observada pela plataforma.

## O cenário

1. `generate_data` cria `orders`, `customers` e `customer_segments` com `customer_id` enviesado — o cliente `C-000001` concentra ~40% das linhas (`--hot-share`).
2. **Commit A** (`src/sales_daily.py`): `orders ⋈ customers` e agregação diária. É o comportamento saudável, usado para formar o baseline.
3. **Commit B** (`scenario/sales_daily_v2.py`): acrescenta o join com `customer_segments` e uma `Window.partitionBy("customer_id")` com `row_number` e soma acumulada. O AQE não divide partições de Window, então a chave quente vira uma task gigante.
4. Toda execução grava um *run profile* em `/Volumes/workspace/eict_platform/landing/run_profiles/<run_id>.json` com a distribuição da chave e o plano físico — é a evidência que a plataforma consome.

## Executar

```bash
export VARS='--var=warehouse_id=<id>'
databricks bundle validate -t dev --profile <seu-profile> $VARS
databricks bundle deploy   -t dev --profile <seu-profile> $VARS
databricks bundle run generate_data -t dev --profile <seu-profile> $VARS
databricks bundle run sales_daily   -t dev --profile <seu-profile> $VARS
```

Cenário completo (baseline, commit B, runs lentos):

```bash
PROFILE=<seu-profile> BASELINE_RUNS=7 bash scenario/run_scenario.sh
```

O script exige árvore git limpa, porque `${bundle.git.commit}` é gravado como parâmetro do job e vira a evidência de mudança. Ele aborta se a versão B não for pelo menos 1,5× mais lenta que a A — premissa A-009.

## Ajustes

| Variável | Efeito |
|----------|--------|
| `scale` | milhões de linhas em `orders` (default 20) |
| `hot_share` | fração das linhas na chave quente (default 0.4) |

Se a regressão for pequena, aumente `scale`; se o run ficar caro demais, reduza. `scenario/expected_rca.json` guarda o resultado esperado do RCA.
