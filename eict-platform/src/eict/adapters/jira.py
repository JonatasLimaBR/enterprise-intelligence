from __future__ import annotations

from dataclasses import dataclass

import requests

TIMEOUT_S = 30
LABEL_PREFIX = "eict-"
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class JiraRetryableError(RuntimeError):
    pass


class JiraPermanentError(RuntimeError):
    pass


@dataclass(frozen=True)
class JiraIssue:
    key: str
    url: str


@dataclass(frozen=True)
class JiraClient:
    base_url: str
    email: str
    token: str
    project_key: str
    issue_type: str = "Task"
    session: requests.Session | None = None

    def find_by_label(self, label: str) -> JiraIssue | None:
        response = self._request(
            "GET",
            "/rest/api/3/search/jql",
            params={"jql": f'project = "{self.project_key}" AND labels = "{label}"', "maxResults": 1},
        )
        issues = response.get("issues", [])
        if not issues:
            return None
        return JiraIssue(key=issues[0]["key"], url=self._browse(issues[0]["key"]))

    def create_issue(self, label: str, summary: str, description: str) -> JiraIssue:
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary[:250],
                "issuetype": {"name": self.issue_type},
                "labels": [label],
                "description": _adf(description),
            }
        }
        response = self._request("POST", "/rest/api/3/issue", json=payload)
        return JiraIssue(key=response["key"], url=self._browse(response["key"]))

    def ensure_issue(self, label: str, summary: str, description: str) -> JiraIssue:
        existing = self.find_by_label(label)
        if existing is not None:
            return existing
        return self.create_issue(label, summary, description)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        session = self.session or requests.Session()
        response = session.request(
            method,
            f"{self.base_url.rstrip('/')}{path}",
            auth=(self.email, self.token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=TIMEOUT_S,
            **kwargs,
        )
        if response.status_code in RETRYABLE_STATUS:
            raise JiraRetryableError(f"jira {response.status_code}: {response.text[:200]}")
        if response.status_code >= 400:
            raise JiraPermanentError(f"jira {response.status_code}: {response.text[:200]}")
        return response.json() if response.content else {}

    def _browse(self, key: str) -> str:
        return f"{self.base_url.rstrip('/')}/browse/{key}"


def label_for(correlation_key: str) -> str:
    return f"{LABEL_PREFIX}{correlation_key}"


def _adf(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line or " "}]}
            for line in text.splitlines()
        ],
    }
