from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eict.domain.models import content_hash

SPEC_VERSION = "1.0"
SCHEMA_VERSION = 1

KNOWN_TYPES = frozenset(
    {
        "asset.discovered",
        "execution.completed",
        "execution.timing",
        "metric.observed",
        "change.committed",
        "incident.created",
        "incident.updated",
        "policy.decision",
        "ai.narrative.rejected",
        "action.requested",
        "action.failed",
    }
)


class InvalidEnvelopeError(ValueError):
    pass


@dataclass(frozen=True)
class Envelope:
    id: str
    source: str
    type: str
    subject: str
    time: datetime
    tenant_id: str
    data: dict[str, Any]
    environment: str = "demo"
    classification: str = "internal"
    schema_version: int = SCHEMA_VERSION
    specversion: str = SPEC_VERSION
    trace_id: str | None = None
    content_hash: str = field(default="")

    @staticmethod
    def create(
        source: str,
        type: str,
        subject: str,
        time: datetime,
        tenant_id: str,
        data: dict[str, Any],
        environment: str = "demo",
    ) -> Envelope:
        if not source or not type or not subject:
            raise InvalidEnvelopeError("source, type and subject are required")
        if type not in KNOWN_TYPES:
            raise InvalidEnvelopeError(f"unknown event type: {type}")
        payload = json.dumps(data, sort_keys=True, default=str)
        return Envelope(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}|{type}|{subject}|{time.isoformat()}")),
            source=source,
            type=type,
            subject=subject,
            time=time,
            tenant_id=tenant_id,
            data=data,
            environment=environment,
            content_hash=content_hash(payload),
        )

    def as_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "specversion": self.specversion,
            "source": self.source,
            "type": self.type,
            "subject": self.subject,
            "time": self.time,
            "tenant_id": self.tenant_id,
            "environment": self.environment,
            "classification": self.classification,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "data": json.dumps(self.data, sort_keys=True, default=str),
            "content_hash": self.content_hash,
        }
