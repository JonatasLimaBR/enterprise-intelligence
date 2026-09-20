from __future__ import annotations

import argparse

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from run_profile import write_profile

JOIN_KEY = "customer_id"
RECENT_ORDERS = 20000


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily sales aggregation")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--landing-dir", required=True)
    parser.add_argument("--git-sha", default="")
    parser.add_argument("--run-id", required=True)
    known, _ = parser.parse_known_args(argv)
    return known


def build_sales_daily(
    orders: DataFrame, customers: DataFrame, segments: DataFrame
) -> DataFrame:
    customer_window = Window.partitionBy(JOIN_KEY).orderBy(F.col("order_ts"))
    recent_window = customer_window.rowsBetween(-RECENT_ORDERS + 1, 0)
    value_window = Window.partitionBy(JOIN_KEY).orderBy(F.col("net_amount").desc())
    enriched = (
        orders.join(customers, JOIN_KEY, "left")
        .join(segments, JOIN_KEY, "left")
        .withColumn("net_amount", F.col("amount") * (1 - F.col("discount_pct") / 100))
        .withColumn("order_rank", F.row_number().over(customer_window))
        .withColumn("running_revenue", F.sum("net_amount").over(customer_window))
        .withColumn("recent_max_ticket", F.max("net_amount").over(recent_window))
        .withColumn("recent_min_ticket", F.min("net_amount").over(recent_window))
        .withColumn("value_rank", F.dense_rank().over(value_window))
        .withColumn("value_percentile", F.percent_rank().over(value_window))
    )
    return enriched.groupBy("order_date", "region", "segment").agg(
        F.sum("net_amount").alias("revenue"),
        F.count("*").alias("orders"),
        F.countDistinct(JOIN_KEY).alias("customers"),
        F.max("order_rank").alias("max_orders_per_customer"),
        F.max("running_revenue").alias("max_running_revenue"),
        F.max("recent_max_ticket").alias("recent_max_ticket"),
        F.min("recent_min_ticket").alias("recent_min_ticket"),
        F.max("value_rank").alias("distinct_ticket_levels"),
        F.avg("value_percentile").alias("avg_value_percentile"),
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    spark = SparkSession.builder.getOrCreate()
    source = f"{args.catalog}.{args.schema}"

    orders = spark.table(f"{source}.orders")
    customers = spark.table(f"{source}.customers")
    segments = spark.table(f"{source}.customer_segments")
    result = build_sales_daily(orders, customers, segments)

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
