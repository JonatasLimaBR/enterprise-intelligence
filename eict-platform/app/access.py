"""Quem pode fazer o quê no console.

Os papéis de cada pessoa vêm de `roles.yaml`, versionado: mudança de acesso passa por PR. O que
cada papel pode fazer é política do código, abaixo. Fora do arquivo, só leitura — ninguém ganha
poder por omissão.

Puro (sem Streamlit nem conector) porque o App é publicado só com a pasta `app/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

OPERADOR = "operador"
ENGENHEIRO_DADOS = "engenheiro_dados"
DATA_STEWARD = "data_steward"
AUDITOR = "auditor"
ROLES = frozenset({OPERADOR, ENGENHEIRO_DADOS, DATA_STEWARD, AUDITOR})

REVIEW_HYPOTHESIS = "review_hypothesis"
ACCEPT_REGIME = "accept_regime"
VIEW_AUDIT = "view_audit"

PERMISSIONS: dict[str, frozenset[str]] = {
    REVIEW_HYPOTHESIS: frozenset({OPERADOR, ENGENHEIRO_DADOS}),
    ACCEPT_REGIME: frozenset({ENGENHEIRO_DADOS}),
    # Segregação: quem audita lê a trilha e não age; quem age não lê a trilha.
    VIEW_AUDIT: frozenset({DATA_STEWARD, AUDITOR}),
}

ROLES_FILE = Path(__file__).resolve().parent / "roles.yaml"


class RolesError(ValueError):
    """Arquivo de papéis inválido: recusado inteiro, ninguém age."""


@dataclass(frozen=True)
class Directory:
    by_email: dict[str, frozenset[str]]
    error: str = ""

    def roles_of(self, email: str | None) -> frozenset[str]:
        return self.by_email.get((email or "").strip().lower(), frozenset())


@dataclass(frozen=True)
class Decision:
    allowed: bool
    actor: str
    roles: frozenset[str]
    action: str
    reason: str


def parse_roles(payload: object) -> dict[str, frozenset[str]]:
    """`users: {email: [papel, …]}`. Qualquer papel desconhecido recusa o arquivo inteiro."""
    if not isinstance(payload, dict) or not isinstance(payload.get("users"), dict):
        raise RolesError("roles.yaml precisa de um mapeamento `users: {email: [papéis]}`")
    saida: dict[str, frozenset[str]] = {}
    for email, papeis in payload["users"].items():
        if not isinstance(papeis, list) or not papeis:
            raise RolesError(f"{email}: lista de papéis vazia ou inválida")
        desconhecidos = sorted(set(papeis) - ROLES)
        if desconhecidos:
            raise RolesError(f"{email}: papel desconhecido: {', '.join(desconhecidos)}")
        saida[str(email).strip().lower()] = frozenset(papeis)
    return saida


def load_directory(path: Path = ROLES_FILE) -> Directory:
    """Falha segura: arquivo ausente ou inválido vira diretório vazio — todos só leitura."""
    try:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return Directory(parse_roles(payload))
    except (OSError, yaml.YAMLError, RolesError) as exc:
        return Directory({}, f"papéis indisponíveis ({exc}); console em modo só leitura")


def authorize(directory: Directory, email: str | None, action: str) -> Decision:
    ator = (email or "").strip().lower()
    if not ator:
        return Decision(False, "desconhecido", frozenset(), action, "identidade não encaminhada pelo Databricks Apps")
    papeis = directory.roles_of(ator)
    permitidos = PERMISSIONS.get(action, frozenset())
    if papeis & permitidos:
        return Decision(True, ator, papeis, action, f"papel {', '.join(sorted(papeis & permitidos))}")
    if not papeis:
        motivo = directory.error or "usuário sem papel: só leitura"
    else:
        motivo = f"papéis {', '.join(sorted(papeis))} não autorizam {action}"
    return Decision(False, ator, papeis, action, motivo)


def can(directory: Directory, email: str | None, action: str) -> bool:
    return authorize(directory, email, action).allowed
