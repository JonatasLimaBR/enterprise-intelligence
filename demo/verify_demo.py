"""Porta de qualidade do kit de demonstração.

Confere o que um revisor humano não consegue garantir lendo: se todo número citado
tem origem declarada em numbers.json, se nenhum segredo vazou, se o roteiro cabe no
tempo, se as imagens referenciadas existem e se a versão em inglês acompanhou o
original.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

NUMBER_RE = re.compile(r"(?<![\w.#-])\d+(?:[.,]\d+)?(?!\.?\d)(?![\w-])")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|<img[^>]+src=\"([^\"]+)\"")
SECRET_PATTERNS = {
    "e-mail pessoal": re.compile(r"[\w.+-]+@(?:gmail|hotmail|outlook|yahoo|live)\.com"),
    "token Databricks": re.compile(r"dapi[0-9a-f]{32}"),
    "token GitHub": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "token Jira": re.compile(r"ATATT[A-Za-z0-9_-]{20,}"),
    "host de workspace": re.compile(r"dbc-[0-9a-f]{8}-[0-9a-f]{4}"),
    "warehouse id": re.compile(r"\b[0-9a-f]{16}\b"),
}
WARNING_KINDS = frozenset({"imagem_faltando"})
IGNORED_LINE_TOKENS = (
    "version",
    "versão",
    "Python",
    "SPEC",
    "ADR",
    "PRD",
    "| ---",
    "|---",
    "<!--",
)
STRUCTURAL_NUMBERS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "2026", "100"}
WORD_BUDGET = 1300
BLOCK_RE = re.compile(r"^##\s+(\d)\.", re.MULTILINE)
EXPECTED_BLOCKS = 6
EXPECTED_QUESTIONS = 10
CAPTURE_FIELDS = ("arquivo", "tela", "estado")


@dataclass(frozen=True)
class Finding:
    file: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.file}: {self.detail}"


def known_values(numbers: dict) -> set[str]:
    values: set[str] = set(STRUCTURAL_NUMBERS)
    for item in numbers["facts"].values():
        raw = str(item["value"])
        values.add(raw)
        values.add(raw.replace(".", ","))
        if raw.endswith(".0"):
            values.add(raw[:-2])
        if "." in raw:
            values.add(raw.rstrip("0").rstrip("."))
            values.add(raw.replace(".", ",").rstrip("0").rstrip(","))
    return values


def check_numbers(path: Path, values: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in _numbers_in(path):
        if number not in values:
            findings.append(
                Finding(path.name, "numero_sem_origem", f"{number} em “{line[:70]}”")
            )
    return findings


LIST_MARKER_RE = re.compile(r"^\s*\d+[.)]\s+")
BLOCK_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</(?:script|style)>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


def readable_text(path: Path) -> str:
    """Texto que uma pessoa lê: em HTML, sem CSS, script nem atributos."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() not in {".html", ".htm"}:
        return text
    return TAG_RE.sub(" ", BLOCK_TAG_RE.sub(" ", text))


def _numbers_in(path: Path):
    for line in readable_text(path).splitlines():
        if any(token in line for token in IGNORED_LINE_TOKENS):
            continue
        scanned = LIST_MARKER_RE.sub("", line)
        for number in NUMBER_RE.findall(scanned):
            yield number, line.strip()


def check_secrets(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8")  # segredo em atributo ou script também conta
    return [
        Finding(path.name, "segredo", f"{label}: {match.group(0)[:24]}")
        for label, pattern in SECRET_PATTERNS.items()
        for match in pattern.finditer(text)
    ]


def check_word_budget(path: Path, budget: int = WORD_BUDGET) -> list[Finding]:
    words = len(path.read_text(encoding="utf-8").split())
    if words > budget:
        return [Finding(path.name, "roteiro_longo", f"{words} palavras (orçamento {budget})")]
    return []


def check_blocks(path: Path, expected: int = EXPECTED_BLOCKS) -> list[Finding]:
    blocks = BLOCK_RE.findall(path.read_text(encoding="utf-8"))
    if len(blocks) != expected:
        return [Finding(path.name, "blocos", f"{len(blocks)} blocos, esperado {expected}")]
    return []


def check_images(path: Path, base: Path) -> list[Finding]:
    findings: list[Finding] = []
    for match in IMAGE_RE.finditer(path.read_text(encoding="utf-8")):
        target = match.group(1) or match.group(2)
        if target.startswith(("http://", "https://", "data:")):
            continue
        if not (base / target).exists():
            findings.append(Finding(path.name, "imagem_faltando", target))
    return findings


def check_questions(path: Path, expected: int = EXPECTED_QUESTIONS) -> list[Finding]:
    rows = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("|") and re.match(r"^\|\s*\d+\s*\|", line)
    ]
    if len(rows) != expected:
        return [Finding(path.name, "perguntas", f"{len(rows)} perguntas, esperado {expected}")]
    return []


def check_captures(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8").lower()
    missing = [field for field in CAPTURE_FIELDS if field not in text]
    if missing:
        return [Finding(path.name, "capturas", f"faltam campos: {', '.join(missing)}")]
    return []


def check_translation_parity(original: Path, translated: Path) -> list[Finding]:
    original_numbers = {number for number, _ in _numbers_in(original)}
    translated_numbers = {number for number, _ in _numbers_in(translated)}
    missing = original_numbers - translated_numbers - STRUCTURAL_NUMBERS
    if missing:
        return [
            Finding(
                translated.name,
                "traducao_defasada",
                f"números ausentes: {', '.join(sorted(missing))}",
            )
        ]
    return []


def run(base: Path) -> list[Finding]:
    numbers_path = base / "numbers.json"
    if not numbers_path.exists():
        return [Finding("numbers.json", "ausente", "rode collect_numbers.sh")]

    numbers = json.loads(numbers_path.read_text(encoding="utf-8"))
    values = known_values(numbers)
    findings: list[Finding] = []

    documents = [
        path
        for path in [
            base / "ROTEIRO.md",
            base / "ROTEIRO.en.md",
            base / "PERGUNTAS.md",
            base / "onepager.html",
            base / "deck.html",
            base.parent / "README.md",
        ]
        if path.exists()
    ]

    for document in documents:
        findings += check_numbers(document, values)
        findings += check_secrets(document)
        findings += check_images(document, document.parent)

    roteiro = base / "ROTEIRO.md"
    if roteiro.exists():
        findings += check_word_budget(roteiro)
        findings += check_blocks(roteiro)
        translated = base / "ROTEIRO.en.md"
        if translated.exists():
            findings += check_translation_parity(roteiro, translated)

    perguntas = base / "PERGUNTAS.md"
    if perguntas.exists():
        findings += check_questions(perguntas)

    capturas = base / "CAPTURAS.md"
    if capturas.exists():
        findings += check_captures(capturas)

    return findings


def split_by_severity(findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    errors = [item for item in findings if item.kind not in WARNING_KINDS]
    warnings = [item for item in findings if item.kind in WARNING_KINDS]
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica os artefatos da demo")
    parser.add_argument("--base", default=str(Path(__file__).parent))
    parser.add_argument(
        "--strict",
        action="store_true",
        help="trata pendências de captura como erro (use antes de publicar)",
    )
    args = parser.parse_args(argv)

    errors, warnings = split_by_severity(run(Path(args.base)))

    for finding in errors:
        print(f"  {finding}")
    for finding in warnings:
        print(f"  {finding} (capture com CAPTURAS.md)")

    if errors:
        print(f"{len(errors)} erro(s)")
        return 1
    if warnings and args.strict:
        print(f"{len(warnings)} captura(s) pendente(s) — modo estrito")
        return 1
    if warnings:
        print(f"kit verificado; {len(warnings)} captura(s) pendente(s)")
        return 0
    print("kit verificado: números com origem, sem segredos, roteiro no orçamento")
    return 0


if __name__ == "__main__":
    sys.exit(main())
