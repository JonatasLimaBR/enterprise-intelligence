from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.spark

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[2]")
        .appName("eict-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    yield session
    session.stop()


def test_run_profile_json_parses_into_expected_columns(spark, tmp_path):
    payload = (FIXTURES / "run_profile.json").read_text(encoding="utf-8")
    source = tmp_path / "run_profiles"
    source.mkdir()
    (source / "987654321.json").write_text(payload, encoding="utf-8")

    df = spark.read.json(str(source))
    row = df.first()

    assert row["run_id"] == "987654321"
    assert row["skew_ratio"] > 10
    assert "Window" in row["plan_operators"]


def test_run_features_join_keeps_runs_without_profile(spark):
    from pyspark.sql import functions as F

    runs = spark.createDataFrame(
        [("run-1", "job-42", 1200.0), ("run-2", "job-42", 3420.0)],
        "run_id string, job_id string, duration_s double",
    )
    profiles = spark.createDataFrame(
        [("run-2", 18.0, 4_000_000)], "run_id string, skew_ratio double, max_key_rows long"
    )

    features = runs.join(profiles, on="run_id", how="left").withColumn(
        "input_rows", F.lit(None).cast("long")
    )

    assert features.count() == 2
    assert features.filter("run_id = 'run-1'").first()["skew_ratio"] is None


def test_envelope_data_is_parseable_as_json(spark):
    from pyspark.sql import functions as F

    payload = json.dumps({"run_id": "7", "duration_s": 3420.0})
    df = spark.createDataFrame([("execution.completed", payload)], "type string, data string")

    parsed = df.withColumn("payload", F.from_json("data", "run_id string, duration_s double"))

    assert parsed.first()["payload"]["duration_s"] == 3420.0


def test_run_features_join_has_no_ambiguous_columns(spark):
    runs = spark.createDataFrame(
        [("run-1", "job-42", "databricks/demo")],
        "run_id string, job_id string, source_ref string",
    )
    profiles = spark.createDataFrame(
        [("run-1", 18.0, "/Volumes/landing/run-1.json")],
        "run_id string, skew_ratio double, source_ref string",
    )

    features = runs.drop("source_ref").join(profiles, on="run_id", how="left")
    names = features.columns

    assert len(names) == len(set(names))
    assert features.first()["source_ref"].startswith("/Volumes")
