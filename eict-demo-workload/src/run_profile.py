from __future__ import annotations

import contextlib
import io
import json
import re
from datetime import datetime, timezone

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

MAX_PLAN_CHARS = 32_000
OPERATOR_RE = re.compile(
    r"(Window|SortMergeJoin|BroadcastHashJoin|ShuffledHashJoin|Exchange hashpartitioning\([^)]*\))"
)


def plan_text(df: DataFrame) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        df.explain(mode="formatted")
    return buffer.getvalue()[:MAX_PLAN_CHARS]


def key_distribution(keyed_input: DataFrame, key: str) -> dict:
    counts = keyed_input.groupBy(key).count()
    stats = counts.agg(
        F.sum("count").alias("left_rows"),
        F.count("*").alias("distinct_keys"),
        F.max("count").alias("max_key_rows"),
        F.percentile_approx("count", 0.5).alias("median_key_rows"),
    ).first()
    hot = counts.orderBy(F.desc("count")).first()
    median_key_rows = max(int(stats["median_key_rows"] or 1), 1)
    left_rows = int(stats["left_rows"] or 0)
    return {
        "left_rows": left_rows,
        "distinct_keys": int(stats["distinct_keys"] or 0),
        "max_key_rows": int(stats["max_key_rows"] or 0),
        "median_key_rows": median_key_rows,
        "skew_ratio": int(stats["max_key_rows"] or 0) / median_key_rows,
        "top_key_share": (int(hot["count"]) / left_rows) if left_rows else 0.0,
        "hot_key": str(hot[key]),
    }


def write_profile(
    result: DataFrame,
    keyed_input: DataFrame,
    key: str,
    right_rows: int,
    run_id: str,
    git_sha: str,
    landing_dir: str,
) -> dict:
    plan = plan_text(result)
    profile = {
        "run_id": run_id,
        "git_sha": git_sha,
        "profiled_at": datetime.now(timezone.utc).isoformat(),
        "key": key,
        "right_rows": right_rows,
        "physical_plan": plan,
        "plan_operators": sorted(set(OPERATOR_RE.findall(plan))),
        **key_distribution(keyed_input, key),
    }
    destination = f"{landing_dir}/run_profiles/{run_id}.json"
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(profile, handle, ensure_ascii=False)
    return profile
