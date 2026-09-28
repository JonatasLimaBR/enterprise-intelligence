"""Detecção de segredos no diff: regex curado + entropia sobre as linhas adicionadas.

Puro. Varre só as linhas `+` do patch e devolve findings com o trecho **mascarado** — o valor cru do
segredo nunca é retornado, persistido nem logado. Determinístico: mesma entrada, mesmos findings.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

HIGH_ENTROPY = "high_entropy"
SEVERITY_MEDIA = "média"


@dataclass(frozen=True)
class SecretPattern:
    name: str
    regex: str
    severity: str


@dataclass(frozen=True)
class SecretScanPolicy:
    patterns: tuple[SecretPattern, ...]
    entropy_min_len: int = 20
    entropy_min_bits: float = 4.0
    mask_prefix: int = 4


@dataclass(frozen=True)
class SecretFinding:
    sha: str
    file: str
    line: int
    pattern_name: str
    severity: str
    masked: str


def mask(value: str, prefix: int) -> str:
    return value[:prefix] + "***"


def shannon_bits(token: str) -> float:
    if not token:
        return 0.0
    frequencias = {char: token.count(char) / len(token) for char in set(token)}
    return -sum(p * math.log2(p) for p in frequencias.values())


def added_lines(patch: str) -> list[str]:
    return [
        line[1:]
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def scan(change, policy: SecretScanPolicy) -> list[SecretFinding]:
    compilados = [(pattern, re.compile(pattern.regex)) for pattern in policy.patterns]
    arquivo = change.files[0] if change.files else ""
    findings: list[SecretFinding] = []
    for numero, linha in enumerate(added_lines(change.patch), start=1):
        casou = False
        for pattern, regex in compilados:
            match = regex.search(linha)
            if match:
                casou = True
                findings.append(
                    SecretFinding(
                        change.sha, arquivo, numero, pattern.name, pattern.severity,
                        mask(match.group(0), policy.mask_prefix),
                    )
                )
        if casou:
            continue
        for token in linha.split():
            if len(token) >= policy.entropy_min_len and shannon_bits(token) >= policy.entropy_min_bits:
                findings.append(
                    SecretFinding(
                        change.sha, arquivo, numero, HIGH_ENTROPY, SEVERITY_MEDIA,
                        mask(token, policy.mask_prefix),
                    )
                )
    return findings
