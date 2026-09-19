# SPEC-001 — Modelo de Domínio e Dados

## Convenções

- IDs: UUID/ULID imutáveis.
- Datas: UTC ISO-8601; timezone original preservado quando relevante.
- Toda mutação: `created_at`, `updated_at`, `created_by`, `version`.
- Evidência: content hash, source ref e classificação.
- Soft delete quando auditoria exigir; hard delete por workflow de privacidade.

## Entidades principais

### Asset

`asset_id`, `tenant_id`, `asset_type`, `name`, `qualified_name`, `environment`, `domain_id`, `owner_refs`, `criticality`, `classification`, `lifecycle_status`, `source_refs`, `attributes`, `valid_from/to`.

### Relationship

`relationship_id`, `from_asset_id`, `type`, `to_asset_id`, `direction`, `confidence`, `assertion_type`, `source`, `observed_at`, `valid_from/to`, `attributes`.

### Observation/Event

Envelope conforme ADR-001. Observação bruta é imutável; evento enriquecido referencia a origem.

### Incident

`incident_id`, `correlation_key`, `title`, `state`, `severity`, `priority`, `detected_at`, `acknowledged_at`, `recovered_at`, `closed_at`, `primary_asset`, `affected_assets`, `sla`, `business_impact`, `owner`, `ticket_refs`, `hypothesis_refs`, `timeline`.

Estados: `detected`, `triaged`, `investigating`, `mitigating`, `monitoring`, `recovered`, `closed`, `cancelled`.

### Hypothesis

`hypothesis_id`, `incident_id`, `statement`, `status`, `confidence`, `supporting_evidence`, `contradicting_evidence`, `missing_evidence`, `proposed_tests`, `generated_by`, `reviewed_by`.

### Evidence

`evidence_id`, `kind`, `source_ref`, `observed_at`, `summary`, `content_ref`, `hash`, `classification`, `redaction_state`, `freshness`.

### Change

`change_id`, `source`, `change_type`, `commit/deploy/config refs`, `assets`, `author`, `provenance`, `window`, `risk_score`, `approvals`, `rollback_ref`.

### Finding

`finding_id`, `fingerprint`, `category`, `scanner`, `rule`, `severity`, `status`, `asset`, `location`, `evidence`, `first/last_seen`, `remediation`, `exception`.

### Action

`action_id`, `action_type`, `target`, `requested_by`, `policy_decision`, `approval_refs`, `idempotency_key`, `dry_run`, `preconditions`, `status`, `result`, `rollback`, `audit_ref`.

### SemanticMetric

`metric_id`, `name`, `definition`, `formula`, `grain`, `dimensions`, `calendar`, `currency`, `sources`, `owner`, `status`, `version`.

### DataContract

`contract_id`, `dataset`, `producer`, `consumers`, `schema_ref`, `compatibility`, `quality_rules`, `freshness`, `availability`, `version`, `state`.

### AIAsset

Subtipos Model, Prompt, Retriever, VectorIndex, Agent e Tool; registram versões, dependency refs, owner, risk tier, evaluation refs e deployments.

## Integridade

- `correlation_key` única por tenant e janela ativa configurada.
- Evidence imutável; correções criam nova versão.
- Scores armazenam inputs e `policy_version`.
- Relacionamento inferido nunca recebe confidence 1.0 sem confirmação.
- Findings deduplicam por fingerprint estável.

## Particionamento

Eventos por tenant/data/tipo; métricas por tenant/asset/data; auditoria por tenant/data. Evitar particionamento por cardinalidade extrema.

