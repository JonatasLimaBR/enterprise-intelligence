from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from eict.domain.contracts import Contract, ContractError, parse_contract

logger = logging.getLogger(__name__)

CONTRACT_GLOB = "*.yaml"


@dataclass(frozen=True)
class LoadOutcome:
    contracts: tuple[Contract, ...]
    errors: tuple[str, ...]

    @property
    def active(self) -> tuple[Contract, ...]:
        return tuple(contract for contract in self.contracts if contract.is_active)


def load_directory(directory: str | Path) -> LoadOutcome:
    """Carrega todos os contratos. Um arquivo inválido não impede os demais."""
    base = Path(directory)
    if not base.exists():
        return LoadOutcome((), (f"diretório de contratos não encontrado: {base}",))

    contracts: list[Contract] = []
    errors: list[str] = []
    for path in sorted(base.glob(CONTRACT_GLOB)):
        try:
            contracts.append(load_file(path))
        except ContractError as exc:
            errors.append(str(exc))
            logger.warning("contrato ignorado: %s", exc)
    return LoadOutcome(tuple(contracts), tuple(errors))


def load_file(path: str | Path) -> Contract:
    target = Path(path)
    try:
        payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractError(f"{target.name}: YAML inválido ({exc})") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{target.name}: o arquivo não contém um mapeamento")
    return parse_contract(payload, source=target.name)
