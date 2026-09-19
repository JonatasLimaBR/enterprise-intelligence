from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
import responses

from eict.adapters import databricks_jobs
from eict.adapters.github import GitHubClient, GitHubError, relevant_patch, to_change
from eict.adapters.jira import (
    JiraClient,
    JiraPermanentError,
    JiraRetryableError,
    label_for,
)
from eict.jobs.dispatch import MAX_ATTEMPTS, OutboxEntry, dispatch_entry, next_backoff

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)
JIRA_BASE = "https://example.atlassian.net"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_job() -> databricks_jobs.MonitoredJob:
    return databricks_jobs.MonitoredJob(job_id="42", name="sales_daily", env_hash="env-abc123")


def test_run_translation_keeps_git_sha_and_duration():
    payload = load_fixture("jobs_run.json")
    base_run = SimpleNamespace(
        run_id=payload["run_id"],
        start_time=payload["start_time"],
        end_time=payload["end_time"],
        state=SimpleNamespace(life_cycle_state="TERMINATED", result_state="SUCCESS"),
        job_parameters=[
            SimpleNamespace(name=item["name"], value=item.get("value"), default=item.get("default"))
            for item in payload["job_parameters"]
        ],
    )

    run = databricks_jobs.to_domain_run(base_run, make_job())

    assert run is not None
    assert run.git_sha == "b" * 40
    assert run.duration_s == 3420.0
    assert run.env_hash == "env-abc123"


def test_running_run_is_ignored():
    base_run = SimpleNamespace(
        run_id=1,
        start_time=1,
        end_time=0,
        state=SimpleNamespace(life_cycle_state="RUNNING", result_state=None),
        job_parameters=[],
    )

    assert databricks_jobs.to_domain_run(base_run, make_job()) is None


def test_environment_hash_is_stable_and_changes_with_spec():
    first = SimpleNamespace(
        environments=[SimpleNamespace(environment_key="default", spec={"environment_version": "2"})],
        performance_target="STANDARD",
    )
    second = SimpleNamespace(
        environments=[SimpleNamespace(environment_key="default", spec={"environment_version": "3"})],
        performance_target="STANDARD",
    )

    assert databricks_jobs.environment_hash(first) == databricks_jobs.environment_hash(first)
    assert databricks_jobs.environment_hash(first) != databricks_jobs.environment_hash(second)


def test_monitored_jobs_filter_by_tag():
    tagged = SimpleNamespace(
        job_id=42,
        settings=SimpleNamespace(
            name="sales_daily", tags={"eict_monitor": "true"}, environments=[], performance_target=None
        ),
    )
    untagged = SimpleNamespace(
        job_id=43,
        settings=SimpleNamespace(name="other", tags={}, environments=[], performance_target=None),
    )
    client = SimpleNamespace(jobs=SimpleNamespace(list=lambda expand_tasks: [tagged, untagged]))

    jobs = databricks_jobs.list_monitored_jobs(client)

    assert [job.job_id for job in jobs] == ["42"]


def test_commit_translation_keeps_only_relevant_patch_lines():
    change = to_change("acme/eict-demo-workload", load_fixture("github_commit.json"))

    assert change.sha == "b" * 40
    assert "src/sales_daily.py" in change.files
    assert "partitionBy" in change.patch
    assert "README" not in change.patch


def test_relevant_patch_is_empty_for_documentation_only():
    files = [{"filename": "README.md", "patch": "+ documentation line"}]

    assert relevant_patch(files) == ""


@responses.activate
def test_github_error_is_raised_on_failure():
    responses.add(responses.GET, "https://api.github.com/repos/acme/demo/commits/abc", status=404)
    client = GitHubClient(repo="acme/demo", token="token")

    with pytest.raises(GitHubError):
        client.commit("abc")


@responses.activate
def test_at012_existing_issue_is_reused():
    label = label_for("key123")
    responses.add(
        responses.GET,
        f"{JIRA_BASE}/rest/api/3/search/jql",
        json={"issues": [{"key": "EICT-1"}]},
        status=200,
    )
    client = JiraClient(JIRA_BASE, "user@example.com", "token", "EICT")

    issue = client.ensure_issue(label, "summary", "description")

    assert issue.key == "EICT-1"
    assert len(responses.calls) == 1


@responses.activate
def test_at012_issue_is_created_once_when_missing():
    responses.add(responses.GET, f"{JIRA_BASE}/rest/api/3/search/jql", json={"issues": []}, status=200)
    responses.add(responses.POST, f"{JIRA_BASE}/rest/api/3/issue", json={"key": "EICT-9"}, status=201)
    client = JiraClient(JIRA_BASE, "user@example.com", "token", "EICT")

    issue = client.ensure_issue(label_for("key123"), "summary", "description")

    assert issue.key == "EICT-9"
    assert issue.url.endswith("/browse/EICT-9")


@responses.activate
def test_at013_server_error_is_retryable():
    responses.add(responses.GET, f"{JIRA_BASE}/rest/api/3/search/jql", status=503, json={})
    client = JiraClient(JIRA_BASE, "user@example.com", "token", "EICT")

    with pytest.raises(JiraRetryableError):
        client.find_by_label("eict-key123")


@responses.activate
def test_client_error_is_permanent():
    responses.add(responses.GET, f"{JIRA_BASE}/rest/api/3/search/jql", status=400, json={})
    client = JiraClient(JIRA_BASE, "user@example.com", "token", "EICT")

    with pytest.raises(JiraPermanentError):
        client.find_by_label("eict-key123")


class _FailingJira:
    def __init__(self, error: Exception):
        self.error = error

    def ensure_issue(self, label, summary, description):
        raise self.error


def test_at013_retry_row_schedules_backoff():
    entry = OutboxEntry("key123", "inc-1", attempts=1, summary="s", description="d")

    row = dispatch_entry(_FailingJira(JiraRetryableError("503")), entry, NOW)

    assert row["status"] == "pending"
    assert row["attempts"] == 2
    assert row["next_attempt_at"] == NOW + next_backoff(2)


def test_at013_exhausted_retries_become_failed():
    entry = OutboxEntry("key123", "inc-1", attempts=MAX_ATTEMPTS - 1, summary="s", description="d")

    row = dispatch_entry(_FailingJira(JiraRetryableError("503")), entry, NOW)

    assert row["status"] == "failed"
    assert row["next_attempt_at"] is None


def test_permanent_error_fails_immediately():
    entry = OutboxEntry("key123", "inc-1", attempts=0, summary="s", description="d")

    row = dispatch_entry(_FailingJira(JiraPermanentError("400")), entry, NOW)

    assert row["status"] == "failed"
    assert row["attempts"] == 1


def test_backoff_grows_and_is_capped():
    assert next_backoff(1) == timedelta(minutes=2)
    assert next_backoff(99) == timedelta(minutes=16)


def test_at014_capability_probe_marks_missing_source():
    from eict.adapters import capabilities

    class _Spark:
        def sql(self, statement):
            raise RuntimeError("TABLE_OR_VIEW_NOT_FOUND")

    capability = capabilities.probe_table(_Spark(), capabilities.BILLING_USAGE)

    assert capability.status == capabilities.NOT_AVAILABLE
    assert capability.is_available is False
    assert capabilities.status_of([capability], capabilities.BILLING_USAGE) is False


def test_capability_probe_marks_available_source():
    from eict.adapters import capabilities

    class _Spark:
        def sql(self, statement):
            return SimpleNamespace(collect=lambda: [])

    capability = capabilities.probe_table(_Spark(), capabilities.TABLE_LINEAGE)

    assert capability.is_available is True


def test_narrator_without_endpoint_returns_no_content():
    from eict.adapters.llm import NarratorClient

    response = NarratorClient(workspace=None, endpoint="").complete("prompt")

    assert response.content is None
    assert response.error == "endpoint_not_configured"


def test_narrator_failure_is_swallowed_into_error():
    from eict.adapters.llm import NarratorClient

    class _Workspace:
        class serving_endpoints:  # noqa: N801
            @staticmethod
            def get_open_ai_client():
                raise requests.ConnectionError("boom")

    response = NarratorClient(workspace=_Workspace(), endpoint="databricks-gpt-oss-120b").complete("p")

    assert response.content is None
    assert response.error == "ConnectionError"
