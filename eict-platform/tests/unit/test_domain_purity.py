from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "eict" / "domain"
FORBIDDEN_ROOTS = {
    "databricks",
    "pyspark",
    "dlt",
    "mlflow",
    "requests",
    "streamlit",
}
ALLOWED_THIRD_PARTY = {"pydantic"}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_at016_domain_never_imports_platform_specific_packages():
    offenders: dict[str, set[str]] = {}
    for path in DOMAIN_DIR.glob("*.py"):
        forbidden = _imported_roots(path) & FORBIDDEN_ROOTS
        if forbidden:
            offenders[path.name] = forbidden

    assert offenders == {}


def test_sc7_domain_does_not_depend_on_adapters():
    offenders = [
        path.name
        for path in DOMAIN_DIR.glob("*.py")
        if "eict.adapters" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_domain_third_party_dependencies_are_allowlisted():
    stdlib_or_local = {"eict", "__future__"}
    used: set[str] = set()
    for path in DOMAIN_DIR.glob("*.py"):
        used |= _imported_roots(path)

    third_party = {
        name
        for name in used
        if name not in stdlib_or_local and name not in _stdlib_names()
    }

    assert third_party <= ALLOWED_THIRD_PARTY


def _stdlib_names() -> set[str]:
    import sys

    return set(sys.stdlib_module_names)
