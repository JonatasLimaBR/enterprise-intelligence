from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MAX_TOKENS = 700
TEMPERATURE = 0.1


@dataclass(frozen=True)
class NarratorResponse:
    content: str | None
    model: str | None = None
    trace_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class NarratorClient:
    workspace: Any
    endpoint: str

    def complete(self, prompt: str) -> NarratorResponse:
        if not self.endpoint:
            return NarratorResponse(content=None, error="endpoint_not_configured")
        try:
            client = self.workspace.serving_endpoints.get_open_ai_client()
            completion = client.chat.completions.create(
                model=self.endpoint,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            return NarratorResponse(
                content=completion.choices[0].message.content,
                model=self.endpoint,
                trace_id=current_trace_id(),
            )
        except Exception as exc:
            logger.warning("narrator endpoint failed: %s", exc)
            return NarratorResponse(content=None, error=type(exc).__name__)


def current_trace_id() -> str | None:
    try:
        import mlflow

        active = mlflow.get_current_active_span()
        return active.trace_id if active is not None else None
    except Exception:
        return None


def enable_tracing(experiment: str | None = None) -> bool:
    try:
        import mlflow

        if experiment:
            mlflow.set_experiment(experiment)
        mlflow.openai.autolog()
        return True
    except Exception as exc:
        logger.info("mlflow tracing unavailable: %s", exc)
        return False
