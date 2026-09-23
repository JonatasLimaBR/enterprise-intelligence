"""O extrator, testado contra o código real do repositório.

O caso central não é sintético: `sales_daily_small.py` calcula `revenue` de duas formas
diferentes no mesmo arquivo, e isso estava lá antes desta feature existir.
"""

from __future__ import annotations

from pathlib import Path

from eict.domain.extraction import (
    AMBIGUA,
    EXTRAIDA,
    NAO_EXTRAIVEL,
    PARCIAL,
    extract,
    module_constants,
)

WORKLOAD = Path(__file__).resolve().parents[3] / "eict-demo-workload" / "src"
SALES = "workspace.eict_workload.sales_daily"


def _codigo(nome: str) -> str:
    return (WORKLOAD / nome).read_text(encoding="utf-8")


def _por_nome(observadas, metric_id: str):
    return [item for item in observadas if item.metric_id == metric_id]


def test_at01_revenue_tem_duas_definicoes_no_mesmo_arquivo():
    """O conflito real: `sum(amount)` no caminho rápido, `sum(net_amount)` no pesado."""
    observadas = extract(_codigo("sales_daily_small.py"), "sales_daily_small.py", SALES)

    revenues = _por_nome(observadas, "revenue")

    assert len(revenues) == 2
    assert len({item.formula_hash for item in revenues}) == 2


def test_at02_withcolumn_e_expandido_ate_as_colunas_de_origem():
    """`sum(net_amount)` só é comparável depois de virar `sum(amount * (1 - discount/100))`."""
    observadas = extract(_codigo("sales_daily.py"), "sales_daily.py", SALES)

    revenue = _por_nome(observadas, "revenue")[0]

    assert revenue.status == EXTRAIDA
    assert "net_amount" not in revenue.formula_hash
    assert "discount_pct" in revenue.formula_hash


def test_at03_a_mesma_formula_em_dois_arquivos_tem_o_mesmo_hash():
    grande = _por_nome(extract(_codigo("sales_daily.py"), "a.py", SALES), "revenue")[0]
    pequeno = [
        item
        for item in _por_nome(
            extract(_codigo("sales_daily_small.py"), "b.py", SALES), "revenue"
        )
        if "discount_pct" in item.formula_hash
    ][0]

    assert grande.formula_hash == pequeno.formula_hash


def test_at04_o_grao_difere_entre_os_dois_caminhos():
    revenues = _por_nome(
        extract(_codigo("sales_daily_small.py"), "sales_daily_small.py", SALES), "revenue"
    )

    graos = {item.grain for item in revenues}

    assert ("order_date", "region") in graos
    assert ("order_date", "region", "segment") in graos


def test_constante_de_modulo_e_resolvida_ao_valor():
    """`countDistinct(JOIN_KEY)` precisa virar `countDistinct("customer_id")`."""
    observadas = extract(_codigo("sales_daily.py"), "sales_daily.py", SALES)

    customers = _por_nome(observadas, "customers")[0]

    assert "JOIN_KEY" not in customers.formula_hash
    assert "customer_id" in customers.formula_hash
    assert customers.status == EXTRAIDA


def test_chaves_de_join_diferentes_nao_viram_equivalentes():
    """A falsa equivalência que o D2 existe para impedir."""
    base = '''
import pyspark.sql.functions as F
JOIN_KEY = "{chave}"

def build(df):
    return df.groupBy("d").agg(F.countDistinct(JOIN_KEY).alias("customers"))
'''
    um = extract(base.format(chave="customer_id"), "a.py", SALES)[0]
    outro = extract(base.format(chave="cust_id"), "b.py", SALES)[0]

    assert um.formula_hash != outro.formula_hash


def test_separador_de_milhar_nao_cria_conflito_falso():
    """`20000` e `20_000` são o mesmo número."""
    base = '''
import pyspark.sql.functions as F
LIMITE = {valor}

def build(df):
    return df.groupBy("d").agg(F.sum(LIMITE).alias("m"))
'''
    um = extract(base.format(valor="20000"), "a.py", SALES)[0]
    outro = extract(base.format(valor="20_000"), "b.py", SALES)[0]

    assert um.formula_hash == outro.formula_hash


def test_at08_metrica_em_sql_puro_nao_e_extraida_nem_some():
    fonte = '''
def build(spark):
    return spark.sql("SELECT sum(amount) AS revenue FROM t GROUP BY d")
'''
    assert extract(fonte, "sql.py", SALES) == ()


def test_at09_ligacao_ambigua_nao_e_adivinhada():
    """Dois `withColumn` para o mesmo nome no mesmo escopo: não dá para escolher."""
    fonte = '''
import pyspark.sql.functions as F

def build(df, flag):
    if flag:
        df = df.withColumn("net", F.col("amount"))
    else:
        df = df.withColumn("net", F.col("amount") * 0.5)
    return df.groupBy("d").agg(F.sum("net").alias("revenue"))
'''
    observada = extract(fonte, "amb.py", SALES)[0]

    assert observada.status == AMBIGUA
    assert "mais de uma defini" in observada.detail


def test_grao_dinamico_e_reportado_como_nao_extraivel():
    fonte = '''
import pyspark.sql.functions as F

def build(df, cols):
    return df.groupBy(*cols).agg(F.sum("amount").alias("revenue"))
'''
    observada = extract(fonte, "din.py", SALES)[0]

    assert observada.status == NAO_EXTRAIVEL
    assert "granularidade" in observada.detail


def test_nome_nao_resolvido_marca_parcial_e_nao_equivalencia():
    fonte = '''
import pyspark.sql.functions as F

def build(df, fator):
    return df.groupBy("d").agg(F.sum(fator).alias("revenue"))
'''
    observada = extract(fonte, "parc.py", SALES)[0]

    assert observada.status == PARCIAL
    assert observada.is_comparable
    assert "fator" in observada.detail


def test_arquivo_invalido_nao_derruba_a_extracao():
    observada = extract("def build(:", "quebrado.py", SALES)[0]

    assert observada.status == NAO_EXTRAIVEL
    assert "não parseável" in observada.detail


def test_constantes_de_modulo_sao_lidas():
    constantes = module_constants(__import__("ast").parse(_codigo("sales_daily.py")))

    assert constantes["JOIN_KEY"].value == "customer_id"


def test_arquivo_sem_agregacao_devolve_vazio():
    assert extract("def build(df):\n    return df\n", "vazio.py", SALES) == ()


def test_linha_de_origem_e_registrada():
    observadas = extract(_codigo("sales_daily.py"), "sales_daily.py", SALES)

    assert all(item.source_line > 0 for item in observadas)


def test_receptor_da_janela_nao_e_descartado():
    """`max(row_number().over(w))` e `max(sum(x).over(w))` não podem colidir.

    Descartar o receptor fazia as duas virarem `over(w)` — falsa equivalência entre
    métricas que calculam coisas diferentes.
    """
    fonte = '''
import pyspark.sql.functions as F
from pyspark.sql import Window

def build(df):
    w = Window.partitionBy("k")
    return (
        df.withColumn("rank", F.row_number().over(w))
        .withColumn("acumulado", F.sum("amount").over(w))
        .groupBy("d")
        .agg(F.max("rank").alias("m1"), F.max("acumulado").alias("m2"))
    )
'''
    observadas = extract(fonte, "w.py", SALES)
    hashes = {item.metric_id: item.formula_hash for item in observadas}

    assert hashes["m1"] != hashes["m2"]


def test_funcao_do_modulo_continua_desembrulhada():
    fonte = '''
import pyspark.sql.functions as F

def build(df):
    return df.groupBy("d").agg(F.sum("amount").alias("m"))
'''
    observada = extract(fonte, "s.py", SALES)[0]

    assert "amount" in observada.formula_hash
