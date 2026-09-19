from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

HOT_CUSTOMER = "C-000001"
CUSTOMER_COUNT = 100_000
SEGMENT_COUNT = 12


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the skewed demo dataset")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--scale", type=float, default=20.0)
    parser.add_argument("--hot-share", type=float, default=0.4)
    known, _ = parser.parse_known_args(argv)
    return known


def build_customers(spark: SparkSession):
    return (
        spark.range(1, CUSTOMER_COUNT + 1)
        .withColumn("customer_id", F.format_string("C-%06d", F.col("id")))
        .withColumn("customer_name", F.concat(F.lit("Cliente "), F.col("id")))
        .withColumn("region", F.element_at(F.array(*[F.lit(region) for region in ("SP", "RJ", "MG", "RS", "BA")]), (F.col("id") % 5 + 1).cast("int")))
        .drop("id")
    )


def build_segments(spark: SparkSession):
    return (
        spark.range(1, CUSTOMER_COUNT + 1)
        .withColumn("customer_id", F.format_string("C-%06d", F.col("id")))
        .withColumn("segment", F.concat(F.lit("SEG-"), (F.col("id") % SEGMENT_COUNT).cast("string")))
        .withColumn("discount_pct", (F.col("id") % SEGMENT_COUNT) * 0.5)
        .drop("id")
    )


def build_orders(spark: SparkSession, scale: float, hot_share: float):
    total_rows = int(scale * 1_000_000)
    return (
        spark.range(0, total_rows)
        .withColumn("order_id", F.format_string("O-%010d", F.col("id")))
        .withColumn("uniform", F.rand(seed=42))
        .withColumn(
            "customer_id",
            F.when(F.col("uniform") < hot_share, F.lit(HOT_CUSTOMER)).otherwise(
                F.format_string("C-%06d", (F.col("id") % CUSTOMER_COUNT) + 1)
            ),
        )
        .withColumn("order_ts", F.expr("timestampadd(SECOND, -cast(id % 2592000 as int), current_timestamp())"))
        .withColumn("order_date", F.to_date("order_ts"))
        .withColumn("amount", F.round(F.rand(seed=7) * 500 + 10, 2))
        .drop("id", "uniform")
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    spark = SparkSession.builder.getOrCreate()
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {args.catalog}.{args.schema}")

    target = f"{args.catalog}.{args.schema}"
    build_customers(spark).write.mode("overwrite").saveAsTable(f"{target}.customers")
    build_segments(spark).write.mode("overwrite").saveAsTable(f"{target}.customer_segments")
    build_orders(spark, args.scale, args.hot_share).write.mode("overwrite").saveAsTable(
        f"{target}.orders"
    )


if __name__ == "__main__":
    main()
