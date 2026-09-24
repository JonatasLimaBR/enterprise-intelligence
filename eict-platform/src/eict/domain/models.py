from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

NOT_AVAILABLE = "not_available"
PENDING = "pending"
AVAILABLE = "available"

ACTIVE_INCIDENT_STATES = frozenset(
    {"detected", "triaged", "investigating", "mitigating", "monitoring"}
)
CLOSED_INCIDENT_STATES = frozenset({"recovered", "closed", "cancelled"})
SUCCESS_STATE = "SUCCESS"


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"{prefix}-{digest[:12]}"


def content_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class Run:
    run_id: str
    job_id: str
    start_time: datetime
    end_time: datetime
    duration_s: float
    result_state: str
    git_sha: str | None = None
    env_hash: str | None = None
    input_rows: int | None = None
    job_parameters: dict[str, str] = field(default_factory=dict)
    setup_s: float | None = None
    execution_s: float | None = None

    @property
    def succeeded(self) -> bool:
        return self.result_state == SUCCESS_STATE


@dataclass(frozen=True)
class RunProfile:
    run_id: str
    key: str
    left_rows: int
    right_rows: int
    distinct_keys: int
    max_key_rows: int
    median_key_rows: int
    skew_ratio: float
    top_key_share: float
    hot_key: str
    plan_operators: tuple[str, ...] = ()
    git_sha: str | None = None
    source_ref: str | None = None


@dataclass(frozen=True)
class RunFeatures:
    run: Run
    profile: RunProfile | None = None

    @property
    def run_id(self) -> str:
        return self.run.run_id

    @property
    def skew_ratio(self) -> float | None:
        return self.profile.skew_ratio if self.profile else None

    @property
    def plan_operators(self) -> tuple[str, ...]:
        return self.profile.plan_operators if self.profile else ()


@dataclass(frozen=True)
class Change:
    sha: str
    repo: str
    author: str
    committed_at: datetime
    message: str
    files: tuple[str, ...] = ()
    patch: str = ""


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: str
    source_ref: str
    observed_at: datetime
    summary: str
    value: Any = None
    hash: str = ""

    @staticmethod
    def create(
        kind: str,
        source_ref: str,
        observed_at: datetime,
        summary: str,
        value: Any = None,
    ) -> Evidence:
        evidence_id = stable_id("ev", kind, source_ref, summary)
        return Evidence(
            evidence_id=evidence_id,
            kind=kind,
            source_ref=source_ref,
            observed_at=observed_at,
            summary=summary,
            value=value,
            hash=content_hash(f"{kind}|{source_ref}|{summary}|{value}"),
        )


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    code: str
    statement: str
    confidence: float
    supporting: tuple[str, ...] = ()
    contradicting: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    rank: int = 0
    status: str = "proposed"
    policy_version: str = ""
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    def with_confidence(self, confidence: float) -> Hypothesis:
        return replace(self, confidence=confidence)

    def with_rank(self, rank: int) -> Hypothesis:
        return replace(self, rank=rank)

    def confirmed_by(self, reviewer: str, at: datetime) -> Hypothesis:
        return replace(self, status="confirmed", reviewed_by=reviewer, reviewed_at=at)

    def rejected_by(self, reviewer: str, at: datetime) -> Hypothesis:
        return replace(self, status="rejected", reviewed_by=reviewer, reviewed_at=at)


@dataclass(frozen=True)
class TimelineEntry:
    entry_id: str
    incident_id: str
    at: datetime
    kind: str
    summary: str
    evidence_ids: tuple[str, ...] = ()
    actor: str = "eict"

    @staticmethod
    def create(
        incident_id: str,
        at: datetime,
        kind: str,
        summary: str,
        evidence_ids: tuple[str, ...] = (),
        actor: str = "eict",
    ) -> TimelineEntry:
        return TimelineEntry(
            entry_id=stable_id("tl", incident_id, kind, at.isoformat(), summary),
            incident_id=incident_id,
            at=at,
            kind=kind,
            summary=summary,
            evidence_ids=evidence_ids,
            actor=actor,
        )


@dataclass(frozen=True)
class Incident:
    incident_id: str
    correlation_key: str
    tenant_id: str
    subject: str
    type: str
    state: str
    severity: str
    first_run_id: str
    last_run_id: str
    detected_at: datetime
    updated_at: datetime
    affected_assets: tuple[str, ...] = ()
    ticket_refs: tuple[str, ...] = ()
    declared_consumers: tuple[str, ...] = ()
    impact_score: float = 0.0
    impact_policy_version: str = ""
    escalated_from: str = ""
    escalation_reason: str = ""
    version: int = 1

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_INCIDENT_STATES

    @property
    def job_id(self) -> str:
        """Compatibilidade: para incidentes de runtime o subject é o job."""
        return self.subject

    @property
    def undeclared_consumers(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.affected_assets) - set(self.declared_consumers)))

    @property
    def unseen_declared_consumers(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.declared_consumers) - set(self.affected_assets)))

    def touch(self, run: Run) -> Incident:
        return replace(
            self,
            last_run_id=run.run_id,
            updated_at=run.end_time,
            version=self.version + 1,
        )

    def touch_at(self, event_id: str, at: datetime) -> Incident:
        return replace(self, last_run_id=event_id, updated_at=at, version=self.version + 1)

    def with_assets(self, assets: tuple[str, ...]) -> Incident:
        return replace(self, affected_assets=assets, version=self.version + 1)

    def with_declared_consumers(self, consumers: tuple[str, ...]) -> Incident:
        return replace(self, declared_consumers=consumers, version=self.version + 1)

    def with_impact(
        self,
        assets: tuple[str, ...],
        score: float,
        policy_version: str,
        severity: str | None = None,
        escalation_reason: str = "",
    ) -> Incident:
        """Registra o raio e, quando houve elevação, de onde a severidade veio.

        `escalated_from` só é preenchido numa elevação de verdade; reaplicar o mesmo
        impacto num incidente já elevado não reescreve a origem nem inventa história.
        """
        subiu = severity is not None and severity != self.severity
        return replace(
            self,
            affected_assets=assets,
            impact_score=score,
            impact_policy_version=policy_version,
            severity=severity or self.severity,
            escalated_from=self.severity if subiu else self.escalated_from,
            escalation_reason=escalation_reason if subiu else self.escalation_reason,
            version=self.version + 1,
        )

    def resolved_at(self, at: datetime) -> Incident:
        """Fecha o incidente porque a condição deixou de existir.

        Usa `recovered`, o estado de fechamento que o sistema já tem para "o problema
        sumiu" — distinto de `closed` (encerrado por decisão) e `cancelled` (aberto por
        engano).
        """
        return replace(self, state="recovered", updated_at=at, version=self.version + 1)

    def with_ticket(self, ticket_ref: str) -> Incident:
        if ticket_ref in self.ticket_refs:
            return self
        return replace(
            self, ticket_refs=(*self.ticket_refs, ticket_ref), version=self.version + 1
        )


@dataclass(frozen=True)
class DiffRow:
    dimension: str
    healthy: str
    current: str
    changed: bool

    @property
    def available(self) -> bool:
        return NOT_AVAILABLE not in (self.healthy, self.current)


@dataclass(frozen=True)
class RunCost:
    run_id: str
    status: str
    dbus: float | None = None
    list_cost_usd: float | None = None
    baseline_cost_usd: float | None = None
    incremental_cost_usd: float | None = None
    source_ref: str | None = None


@dataclass(frozen=True)
class RuleResult:
    result_id: str
    contract_id: str
    rule_id: str
    asset: str
    dimension: str
    status: str
    threshold: str
    severity: str
    window: str
    query_hash: str
    evaluated_at: datetime
    numerator: int = 0
    denominator: int = 0
    sample: tuple[str, ...] = ()
    error_message: str | None = None
    detail: str = ""

    @property
    def ratio(self) -> float:
        return self.numerator / self.denominator if self.denominator else 0.0

    @property
    def is_violation(self) -> bool:
        return self.status == "violated"

    @property
    def is_error(self) -> bool:
        return self.status == "evaluation_error"

    @property
    def is_blocking(self) -> bool:
        return self.is_violation and self.severity == "blocking"

    def summary(self) -> str:
        if self.is_error:
            return f"{self.rule_id}: não foi possível avaliar ({self.error_message})"
        if self.detail:
            return f"{self.rule_id}: {self.detail}"
        return (
            f"{self.rule_id}: {self.numerator} de {self.denominator} linhas "
            f"({self.ratio:.2%}) contra limite {self.threshold}"
        )
