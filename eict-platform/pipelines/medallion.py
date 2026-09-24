from __future__ import annotations

import dlt
from pyspark.sql import functions as F

LANDING_DIR = spark.conf.get("eict.landing_dir")
BRONZE_TABLE = spark.conf.get("eict.bronze_table")

RUN_SCHEMA = """
    run_id STRING, job_id STRING, job_name STRING, start_time STRING, end_time STRING,
    duration_s DOUBLE, result_state STRING, git_sha STRING, env_hash STRING,
    job_parameters MAP<STRING, STRING>
"""
TIMING_SCHEMA = """
    run_id STRING, job_id STRING, setup_s DOUBLE, execution_s DOUBLE
"""
CHANGE_SCHEMA = """
    sha STRING, repo STRING, author STRING, message STRING,
    files ARRAY<STRING>, patch STRING
"""


@dlt.view(name="observations")
def observations():
    return spark.readStream.table(BRONZE_TABLE)


@dlt.table(name="runs", comment="Canonical job runs from the Jobs API")
@dlt.expect_or_drop("has_identity", "run_id IS NOT NULL AND job_id IS NOT NULL")
@dlt.expect_or_drop("non_negative_duration", "duration_s >= 0")
def runs():
    parsed = (
        dlt.read_stream("observations")
        .filter(F.col("type") == "execution.completed")
        .withColumn("payload", F.from_json("data", RUN_SCHEMA))
    )
    return parsed.select(
        F.col("payload.run_id").alias("run_id"),
        F.col("payload.job_id").alias("job_id"),
        F.col("payload.job_name").alias("job_name"),
        F.col("payload.start_time").cast("timestamp").alias("start_time"),
        F.col("payload.end_time").cast("timestamp").alias("end_time"),
        F.col("payload.duration_s").alias("duration_s"),
        F.col("payload.result_state").alias("result_state"),
        F.col("payload.git_sha").alias("git_sha"),
        F.col("payload.env_hash").alias("env_hash"),
        F.col("payload.job_parameters").alias("job_parameters"),
        F.col("time").alias("observed_at"),
        F.col("source").alias("source_ref"),
    )


@dlt.table(name="run_timings", comment="Setup and execution time per run, summed over tasks")
@dlt.expect_or_drop("has_identity", "run_id IS NOT NULL")
@dlt.expect_or_drop("non_negative_execution", "execution_s >= 0")
def run_timings():
    # Evento próprio (execution.timing): o id do envelope ignora o payload, então o tempo
    # não podia viajar como campo novo de execution.completed sem ser descartado no bronze.
    parsed = (
        dlt.read_stream("observations")
        .filter(F.col("type") == "execution.timing")
        .withColumn("payload", F.from_json("data", TIMING_SCHEMA))
    )
    return parsed.select(
        F.col("payload.run_id").alias("run_id"),
        F.col("payload.setup_s").alias("setup_s"),
        F.col("payload.execution_s").alias("execution_s"),
        F.col("time").alias("observed_at"),
    )


@dlt.table(name="changes", comment="Commits correlated to monitored jobs")
@dlt.expect_or_drop("valid_sha", "sha RLIKE '^[0-9a-f]{40}$'")
def changes():
    parsed = (
        dlt.read_stream("observations")
        .filter(F.col("type") == "change.committed")
        .withColumn("payload", F.from_json("data", CHANGE_SCHEMA))
    )
    return parsed.select(
        F.col("payload.sha").alias("sha"),
        F.col("payload.repo").alias("repo"),
        F.col("payload.author").alias("author"),
        F.col("time").alias("committed_at"),
        F.col("payload.message").alias("message"),
        F.col("payload.files").alias("files"),
        F.col("payload.patch").alias("patch"),
    )


@dlt.table(name="run_profiles", comment="Run profiles emitted by instrumented workloads")
@dlt.expect_or_drop("valid_profile", "run_id IS NOT NULL AND skew_ratio >= 1")
def run_profiles():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaHints", "max_key_rows LONG, median_key_rows LONG, skew_ratio DOUBLE")
        .load(f"{LANDING_DIR}/run_profiles")
        .withColumn("source_ref", F.col("_metadata.file_path"))
        .withColumn("_ingested_at", F.current_timestamp())
        .drop("_rescued_data")
    )


@dlt.table(name="run_features", comment="Run level features consumed by the correlator")
def run_features():
    runs_df = dlt.read("runs").drop("source_ref")
    profiles_df = dlt.read("run_profiles").drop("git_sha")
    timings_df = dlt.read("run_timings").drop("observed_at").dropDuplicates(["run_id"])
    return (
        runs_df.join(profiles_df, on="run_id", how="left")
        .join(timings_df, on="run_id", how="left")
        .withColumn("input_rows", F.col("left_rows"))
        .select(
            "run_id",
            "job_id",
            "job_name",
            "start_time",
            "end_time",
            "duration_s",
            "setup_s",
            "execution_s",
            "result_state",
            "git_sha",
            "env_hash",
            "job_parameters",
            "input_rows",
            "key",
            "left_rows",
            "right_rows",
            "distinct_keys",
            "max_key_rows",
            "median_key_rows",
            "skew_ratio",
            "top_key_share",
            "hot_key",
            "plan_operators",
            "source_ref",
        )
    )
