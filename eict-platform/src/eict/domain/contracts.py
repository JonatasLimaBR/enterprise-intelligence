from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError, field_validator

SUPPORTED_DIMENSIONS = frozenset(
    {"completeness", "uniqueness", "validity", "freshness", "volume", "schema", "referential"}
)
SEVERITIES = frozenset({"info", "warning", "critical", "blocking"})
ACTIVE_STATUSES = frozenset({"active", "approved"})
DEFAULT_WINDOW = "current_state"


class ContractError(ValueError):
    """Contrato malformado: nenhuma regra dele é executada."""


class Rule(BaseModel):
    rule_id: str = Field(min_length=1)
    dimension: str
    threshold: str = Field(min_length=1)
    severity: str
    owner: str = Field(min_length=1)
    expression: str = ""
    window: str = DEFAULT_WINDOW
    description: str = ""

    @field_validator("dimension")
    @classmethod
    def known_dimension(cls, value: str) -> str:
        if value not in SUPPORTED_DIMENSIONS:
            raise ValueError(
                f"dimensão não suportada: {value} (use uma de {sorted(SUPPORTED_DIMENSIONS)})"
            )
        return value

    @field_validator("severity")
    @classmethod
    def known_severity(cls, value: str) -> str:
        if value not in SEVERITIES:
            raise ValueError(f"severidade inválida: {value} (use uma de {sorted(SEVERITIES)})")
        return value

    @property
    def is_blocking(self) -> bool:
        return self.severity == "blocking"


class ColumnSpec(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    required: bool = False


class Contract(BaseModel):
    contract_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: str
    owner: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    asset: str = Field(min_length=1)
    quality: list[Rule] = Field(min_length=1)
    classification: str = "internal"
    consumers: list[str] = Field(default_factory=list)
    columns: list[ColumnSpec] = Field(default_factory=list)
    slo: dict[str, str] = Field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def freshness_slo(self) -> str | None:
        return self.slo.get("freshness")

    def rules_for(self, dimension: str) -> list[Rule]:
        return [rule for rule in self.quality if rule.dimension == dimension]


def parse_contract(payload: dict, source: str = "<memória>") -> Contract:
    """Converte o YAML já lido em Contract, ou falha apontando o arquivo."""
    try:
        return Contract.model_validate(payload)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ContractError(f"{source}: {details}") from exc


def summary_row(contract: Contract, loaded_at) -> dict:
    return {
        "contract_id": contract.contract_id,
        "version": contract.version,
        "status": contract.status,
        "owner": contract.owner,
        "producer": contract.producer,
        "asset": contract.asset,
        "classification": contract.classification,
        "declared_consumers": list(contract.consumers),
        "rule_count": len(contract.quality),
        "loaded_at": loaded_at,
    }
