from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import requests

from eict.domain.models import Change

API_ROOT = "https://api.github.com"
MAX_PATCH_CHARS = 20_000
TIMEOUT_S = 20
RELEVANT_PATCH_TOKENS = ("join", "Window", "partitionBy", "skew")


class GitHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubClient:
    repo: str
    token: str
    session: requests.Session | None = None
    api_root: str = API_ROOT

    def commit(self, sha: str) -> Change:
        session = self.session or requests.Session()
        response = session.get(
            f"{self.api_root}/repos/{self.repo}/commits/{sha}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=TIMEOUT_S,
        )
        if response.status_code != 200:
            raise GitHubError(f"github {response.status_code} for commit {sha}")
        return to_change(self.repo, response.json())


def to_change(repo: str, payload: dict) -> Change:
    commit = payload.get("commit", {})
    author = commit.get("author", {}) or {}
    files = tuple(item.get("filename", "") for item in payload.get("files", []) or ())
    return Change(
        sha=payload.get("sha", ""),
        repo=repo,
        author=author.get("email", "") or author.get("name", ""),
        committed_at=_parse_date(author.get("date")),
        message=commit.get("message", ""),
        files=files,
        patch=relevant_patch(payload.get("files", []) or []),
    )


def relevant_patch(files: list[dict]) -> str:
    fragments: list[str] = []
    for item in files:
        patch = item.get("patch") or ""
        lines = [
            line
            for line in patch.splitlines()
            if line.startswith(("+", "-")) and any(token in line for token in RELEVANT_PATCH_TOKENS)
        ]
        if lines:
            fragments.append(f"--- {item.get('filename', '')}\n" + "\n".join(lines))
    return "\n".join(fragments)[:MAX_PATCH_CHARS]


def _parse_date(value: str | None) -> datetime:
    if not value:
        raise GitHubError("commit without author date")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
