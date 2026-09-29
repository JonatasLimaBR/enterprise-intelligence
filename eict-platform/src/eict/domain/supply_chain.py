"""SBOM e matching de advisories: parse de manifestos + comparação de versão.

Puro. Extrai `(pacote, lower_bound)` de pyproject/requirements, casa contra um catálogo de advisories
(`lower_bound < fixed_in`) e varre as linhas de manifesto adicionadas no patch. Determinístico.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass

DEP_SPEC = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?:==|>=|<=|~=|!=)\s*([0-9][0-9.]*)"
)


@dataclass(frozen=True)
class Advisory:
    package: str
    fixed_in: str
    severity: str
    cve: str
    title: str = ""


@dataclass(frozen=True)
class Dependency:
    package: str
    lower_bound: str
    file: str


@dataclass(frozen=True)
class DependencyFinding:
    sha: str
    package: str
    declared: str
    fixed_in: str
    severity: str
    cve: str
    file: str


def version_tuple(value: str) -> tuple[int, ...]:
    partes: list[int] = []
    for token in value.split("."):
        numero = re.match(r"\d+", token)
        partes.append(int(numero.group()) if numero else 0)
    return tuple(partes) or (0,)


def version_lt(a: str, b: str) -> bool:
    ta, tb = version_tuple(a), version_tuple(b)
    tamanho = max(len(ta), len(tb))
    return ta + (0,) * (tamanho - len(ta)) < tb + (0,) * (tamanho - len(tb))


def _dep_from_line(line: str, file: str) -> Dependency | None:
    limpo = line.strip().strip('"').strip("'").rstrip(",").strip('"').strip("'")
    match = DEP_SPEC.match(limpo)
    if not match:
        return None
    return Dependency(match.group(1).lower(), match.group(2), file)


def parse_dependencies(text: str, filename: str) -> list[Dependency]:
    if filename.endswith(".toml"):
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return []
        projeto = data.get("project", {}) if isinstance(data, dict) else {}
        linhas = list(projeto.get("dependencies", []) or [])
        for extra in (projeto.get("optional-dependencies", {}) or {}).values():
            linhas += list(extra or [])
        return [dep for linha in linhas if (dep := _dep_from_line(str(linha), filename))]
    return [dep for linha in text.splitlines() if (dep := _dep_from_line(linha, filename))]


def match(dep: Dependency, advisories: dict[str, tuple[Advisory, ...]]) -> list[Advisory]:
    return [adv for adv in advisories.get(dep.package, ()) if version_lt(dep.lower_bound, adv.fixed_in)]


def scan_change(change, advisories: dict[str, tuple[Advisory, ...]]) -> list[DependencyFinding]:
    arquivo = change.files[0] if change.files else ""
    findings: list[DependencyFinding] = []
    for line in change.patch.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        dep = _dep_from_line(line[1:], arquivo)
        if dep is None:
            continue
        for adv in match(dep, advisories):
            findings.append(
                DependencyFinding(
                    change.sha, dep.package, dep.lower_bound, adv.fixed_in, adv.severity, adv.cve, dep.file
                )
            )
    return findings
