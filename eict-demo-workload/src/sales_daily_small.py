from __future__ import annotations

import argparse

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from run_profile import write_profile

JOIN_KEY = "customer_id"
RECENT_ORDERS = 20_000


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily sales aggregation (demo trigger)")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--landing-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--git-sha", default="")
    parser.add_argument("--heavy", default="false")
    known, _ = parser.parse_known_args(argv)
    return known


def is_heavy(flag: str) -> bool:
    return flag.strip().lower() in {"true", "1", "yes", "sim"}


def build(orders: DataFrame, customers: DataFrame, segments: DataFrame, heavy: bool) -> DataFrame:
    enriched = orders.join(customers, JOIN_KEY, "left")
    if not heavy:
        return enriched.groupBy("order_date", "region").agg(
            F.sum("amount").alias("revenue"),
            F.count("*").alias("orders"),
            F.countDistinct(JOIN_KEY).alias("customers"),
        )

    customer_window = Window.partitionBy(JOIN_KEY).orderBy(F.col("order_ts"))
    recent_window = customer_window.rowsBetween(-RECENT_ORDERS + 1, 0)
    value_window = Window.partitionBy(JOIN_KEY).orderBy(F.col("net_amount").desc())
    return (
        enriched.join(segments, JOIN_KEY, "left")
        .withColumn("net_amount", F.col("amount") * (1 - F.col("discount_pct") / 100))
        .withColumn("order_rank", F.row_number().over(customer_window))
        .withColumn("recent_max_ticket", F.max("net_amount").over(recent_window))
        .withColumn("value_rank", F.dense_rank().over(value_window))
        .groupBy("order_date", "region", "segment")
        .agg(
            F.sum("net_amount").alias("revenue"),
            F.count("*").alias("orders"),
            F.countDistinct(JOIN_KEY).alias("customers"),
            F.max("order_rank").alias("max_orders_per_customer"),
            F.max("recent_max_ticket").alias("recent_max_ticket"),
            F.max("value_rank").alias("distinct_ticket_levels"),
        )
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    spark = SparkSession.builder.getOrCreate()
    source = f"{args.catalog}.{args.schema}"
    heavy = is_heavy(args.heavy)

    orders = spark.table(f"{source}.orders_small")
    customers = spark.table(f"{source}.customers")
    segments = spark.table(f"{source}.customer_segments")
    result = build(orders, customers, segments, heavy)

    result.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        f"{source}.sales_daily_small"
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
