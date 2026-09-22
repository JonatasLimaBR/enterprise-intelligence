"""Provoca violações reais de contrato, de forma reversível.

Cada modo faz backup da tabela antes de alterar; `--mode restore` desfaz tudo.
Sem isso, a demo destruiria o cenário de regressão que já está provado.
"""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

MODES = ("completeness", "uniqueness", "referential", "freshness", "restore")
ORDERS = "orders"
CUSTOMERS = "customers"
SALES_DAILY = "sales_daily"
BACKUP_SUFFIX = "_contract_backup"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provoca violação de contrato para a demo")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--share", type=float, default=0.08)
    known, _ = parser.parse_known_args(argv)
    return known


def qualified(args: argparse.Namespace, table: str) -> str:
    return f"{args.catalog}.{args.schema}.{table}"


def _fatia(coluna: str, share: float) -> str:
    """Fatia determinística das linhas: o Delta recusa rand() em UPDATE."""
    return f"abs(hash({coluna})) % 10000 < {int(share * 10000)}"


def backup(spark: SparkSession, table: str) -> None:
    spark.sql(f"CREATE TABLE IF NOT EXISTS {table}{BACKUP_SUFFIX} AS SELECT * FROM {table}")


def restore(spark: SparkSession, table: str) -> bool:
    backup_table = f"{table}{BACKUP_SUFFIX}"
    if not spark.catalog.tableExists(backup_table):
        return False
    spark.sql(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM {backup_table}")
    spark.sql(f"DROP TABLE {backup_table}")
    return True


def break_completeness(spark: SparkSession, table: str, share: float) -> str:
    """Apaga o cliente de uma fração dos pedidos: quebra a regra de completeness."""
    backup(spark, table)
    spark.sql(f"UPDATE {table} SET customer_id = NULL WHERE {_fatia('order_id', share)}")
    afetadas = spark.sql(f"SELECT count(*) AS n FROM {table} WHERE customer_id IS NULL").first()["n"]
    return f"{afetadas} pedidos ficaram sem cliente"


def break_uniqueness(spark: SparkSession, table: str, share: float) -> str:
    """Duplica pedidos: quebra a regra de unicidade da chave."""
    backup(spark, table)
    duplicados = spark.table(table).sample(fraction=min(share, 0.05), seed=7)
    duplicados.write.mode("append").saveAsTable(table)
    return f"{duplicados.count()} pedidos duplicados"


def break_referential(spark: SparkSession, table: str, share: float) -> str:
    """Aponta pedidos para clientes inexistentes: quebra a integridade referencial."""
    backup(spark, table)
    spark.sql(
        f"""
        UPDATE {table}
        SET customer_id = concat('C-ORFAO-', cast(abs(hash(order_id)) % 1000 AS string))
        WHERE {_fatia('order_id', share)}
        """
    )
    return "pedidos passaram a apontar para clientes inexistentes"


def break_freshness(spark: SparkSession, table: str) -> str:
    """Congela a tabela agregada: o contrato exige escrita a cada 30 min."""
    backup(spark, table)
    return (
        "nenhuma escrita foi feita; pause o job sales_daily e aguarde o SLO de freshness "
        "estourar (o backup permite restaurar o estado anterior)"
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    spark = SparkSession.builder.getOrCreate()
    orders = qualified(args, ORDERS)
    sales = qualified(args, SALES_DAILY)

    if args.mode == "restore":
        restauradas = [table for table in (orders, sales) if restore(spark, table)]
        print(f"restauradas: {', '.join(restauradas) if restauradas else 'nenhuma tabela'}")
        return

    acoes = {
        "completeness": lambda: break_completeness(spark, orders, args.share),
        "uniqueness": lambda: break_uniqueness(spark, orders, args.share),
        "referential": lambda: break_referential(spark, orders, args.share),
        "freshness": lambda: break_freshness(spark, sales),
    }
    print(f"modo {args.mode}: {acoes[args.mode]()}")
    print("desfaça com --mode restore")


if __name__ == "__main__":
    main()
