from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from eict.domain.models import Change, Run, RunFeatures, RunProfile

BASE_TIME = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)
JOB_ID = "job-42"
TENANT = "demo"
HEALTHY_SHA = "a" * 40
REGRESSION_SHA = "b" * 40
ENV_HASH = "env-v2-standard"


def make_run(
    index: int,
    duration_s: float,
    result_state: str = "SUCCESS",
    git_sha: str = HEALTHY_SHA,
    input_rows: int | None = 10_000_000,
    env_hash: str | None = ENV_HASH,
) -> Run:
    start = BASE_TIME + timedelta(hours=index)
    return Run(
        run_id=f"run-{index}",
        job_id=JOB_ID,
        start_time=start,
        end_time=start + timedelta(seconds=duration_s),
        duration_s=duration_s,
        result_state=result_state,
        git_sha=git_sha,
        env_hash=env_hash,
        input_rows=input_rows,
        job_parameters={"scale": "10", "git_sha": git_sha},
    )


def make_profile(
    run_id: str,
    skew_ratio: float = 2.0,
    operators: tuple[str, ...] = ("SortMergeJoin",),
    git_sha: str = HEALTHY_SHA,
) -> RunProfile:
    median_rows = 1_000
    return RunProfile(
        run_id=run_id,
        key="customer_id",
        left_rows=10_000_000,
        right_rows=100_000,
        distinct_keys=100_000,
        max_key_rows=int(median_rows * skew_ratio),
        median_key_rows=median_rows,
        skew_ratio=skew_ratio,
        top_key_share=0.4 if skew_ratio >= 10 else 0.01,
        hot_key="C-0001",
        plan_operators=operators,
        git_sha=git_sha,
        source_ref=f"/Volumes/landing/run_profiles/{run_id}.json",
    )


@pytest.fixture
def healthy_history() -> list[Run]:
    return [make_run(index, duration_s=1200 + index * 10) for index in range(7)]


@pytest.fixture
def healthy_features() -> RunFeatures:
    run = make_run(6, duration_s=1260)
    return RunFeatures(run=run, profile=make_profile(run.run_id))


@pytest.fixture
def regressed_features() -> RunFeatures:
    run = make_run(7, duration_s=3420, git_sha=REGRESSION_SHA)
    profile = make_profile(
        run.run_id,
        skew_ratio=18.0,
        operators=("SortMergeJoin", "Window", "Exchange hashpartitioning(customer_id)"),
        git_sha=REGRESSION_SHA,
    )
    return RunFeatures(run=run, profile=profile)


@pytest.fixture
def commit_b() -> Change:
    return Change(
        sha=REGRESSION_SHA,
        repo="acme/eict-demo-workload",
        author="dev@example.com",
        committed_at=BASE_TIME + timedelta(hours=6, minutes=30),
        message="feat: add segment join and per-customer ranking",
        files=("src/sales_daily.py",),
        patch="+    .join(segments, 'customer_id')\n+    Window.partitionBy('customer_id')",
    )


@pytest.fixture
def unrelated_commit() -> Change:
    return Change(
        sha="c" * 40,
        repo="acme/eict-demo-workload",
        author="dev@example.com",
        committed_at=BASE_TIME + timedelta(hours=6, minutes=45),
        message="docs: update readme",
        files=("README.md",),
        patch="+ documentation only",
    )
