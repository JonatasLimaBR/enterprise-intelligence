from __future__ import annotations

import argparse

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from run_profile import write_profile

JOIN_KEY = "customer_id"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily sales aggregation")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--landing-dir", required=True)
    parser.add_argument("--git-sha", default="")
    parser.add_argument("--run-id", required=True)
    known, _ = parser.parse_known_args(argv)
    return known


def build_sales_daily(orders: DataFrame, customers: DataFrame) -> DataFrame:
    return (
        orders.join(customers, JOIN_KEY, "left")
        .groupBy("order_date", "region")
        .agg(
            F.sum("amount").alias("revenue"),
            F.count("*").alias("orders"),
            F.countDistinct(JOIN_KEY).alias("customers"),
        )
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    spark = SparkSession.builder.getOrCreate()
    source = f"{args.catalog}.{args.schema}"

    orders = spark.table(f"{source}.orders")
    customers = spark.table(f"{source}.customers")
    result = build_sales_daily(orders, customers)

    result.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        f"{source}.sales_daily"
    )

    write_profile(
        result=result,
        keyed_input=orders.select(JOIN_KEY),
        key=JOIN_KEY,
        right_rows=customers.count(),
        run_id=args.run_id,
        git_sha=args.git_sha,
        landing_dir=args.landing_dir,
    )


if __name__ == "__main__":
    main()
