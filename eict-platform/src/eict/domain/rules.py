from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from eict.domain.contracts import ColumnSpec, Contract, Rule

SAMPLE_LIMIT = 5
PASSED = "passed"
VIOLATED = "violated"
EVALUATION_ERROR = "evaluation_error"

THRESHOLD_RE = re.compile(r"^(?P<op>>=|<=|>|<|==)?\s*(?P<value>[\d.]+)\s*(?P<unit>%)?$")
REFERENTIAL_RE = re.compile(r"^(?P<child>\w+)\s+in\s+(?P<parent>[\w.]+)\.(?P<key>\w+)$", re.I)
DURATION_RE = re.compile(r"^(?P<value>\d+)\s*(?P<unit>[smhd])$", re.I)
DURATION_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class RuleCompilationError(ValueError):
    """A regra não pôde ser traduzida em consulta."""


@dataclass(frozen=True)
class CompiledRule:
    rule_id: str
    asset: str
    dimension: str
    sql: str

    @property
    def query_hash(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()[:16]


def compile_rule(rule: Rule, contract: Contract) -> CompiledRule:
    compilers = {
        "completeness": _completeness,
        "uniqueness": _uniqueness,
        "validity": _validity,
        "referential": _referential,
        "volume": _volume,
        "freshness": _freshness,
    }
    if rule.dimension == "schema":
        raise RuleCompilationError(
            "a dimensão schema é avaliada contra o catálogo, não por consulta"
        )
    compiler = compilers.get(rule.dimension)
    if compiler is None:
        raise RuleCompilationError(f"sem compilador para a dimensão {rule.dimension}")
    return CompiledRule(rule.rule_id, contract.asset, rule.dimension, compiler(rule, contract))


def evaluate(rule: Rule, numerator: int, denominator: int) -> str:
    """Compara a proporção de violações com o limite declarado."""
    if denominator <= 0:
        return PASSED
    ratio = numerator / denominator
    return VIOLATED if ratio > violation_limit(rule.threshold) else PASSED


def violation_limit(threshold: str) -> float:
    """Converte o limite declarado na fração máxima de violação tolerada.

    ">= 99.9%" tolera 0.1% de violação; "<= 0.1%" tolera os mesmos 0.1%.
    """
    match = THRESHOLD_RE.match(threshold.strip())
    if match is None:
        raise RuleCompilationError(f"limite inválido: {threshold}")
    value = float(match.group("value"))
    if match.group("unit") == "%":
        value = value / 100
    operator = match.group("op") or ">="
    return round(1 - value, 10) if operator in {">=", ">"} else value


def parse_duration_seconds(duration: str) -> int:
    match = DURATION_RE.match(duration.strip())
    if match is None:
        raise RuleCompilationError(f"duração inválida: {duration}")
    return int(match.group("value")) * DURATION_SECONDS[match.group("unit").lower()]


def missing_columns(expected: list[ColumnSpec], actual: dict[str, str]) -> list[str]:
    return [column.name for column in expected if column.name not in actual]


def type_mismatches(expected: list[ColumnSpec], actual: dict[str, str]) -> list[str]:
    return [
        f"{column.name}: contrato={column.type} tabela={actual[column.name]}"
        for column in expected
        if column.name in actual and not _same_type(column.type, actual[column.name])
    ]


def undeclared_columns(expected: list[ColumnSpec], actual: dict[str, str]) -> list[str]:
    declared = {column.name for column in expected}
    return sorted(name for name in actual if name not in declared)


def _same_type(declared: str, actual: str) -> bool:
    return _normalize_type(declared) == _normalize_type(actual)


def _normalize_type(value: str) -> str:
    simplified = value.strip().lower().split("(")[0]
    aliases = {"integer": "int", "long": "bigint", "text": "string", "varchar": "string"}
    return aliases.get(simplified, simplified)


def _completeness(rule: Rule, contract: Contract) -> str:
    column = _required_expression(rule)
    return _normalize(f"""
        SELECT
          count_if({column} IS NULL) AS numerator,
          count(*) AS denominator,
          slice(array_agg(CASE WHEN {column} IS NULL THEN to_json(struct(*)) END), 1, {SAMPLE_LIMIT})
            AS sample
        FROM {contract.asset}
    """)


def _uniqueness(rule: Rule, contract: Contract) -> str:
    column = _required_expression(rule)
    return _normalize(f"""
        WITH counted AS (
          SELECT {column} AS chave, count(*) AS ocorrencias
          FROM {contract.asset}
          GROUP BY {column}
        )
        SELECT
          coalesce(sum(CASE WHEN ocorrencias > 1 THEN ocorrencias ELSE 0 END), 0) AS numerator,
          coalesce(sum(ocorrencias), 0) AS denominator,
          slice(array_agg(CASE WHEN ocorrencias > 1 THEN to_json(struct(chave, ocorrencias)) END),
                1, {SAMPLE_LIMIT}) AS sample
        FROM counted
    """)


def _validity(rule: Rule, contract: Contract) -> str:
    condition = _required_expression(rule)
    return _normalize(f"""
        SELECT
          count_if(NOT ({condition})) AS numerator,
          count(*) AS denominator,
          slice(array_agg(CASE WHEN NOT ({condition}) THEN to_json(struct(*)) END), 1, {SAMPLE_LIMIT})
            AS sample
        FROM {contract.asset}
    """)


def _referential(rule: Rule, contract: Contract) -> str:
    match = REFERENTIAL_RE.match(_required_expression(rule))
    if match is None:
        raise RuleCompilationError(
            f"expressão referencial inválida: {rule.expression} "
            "(use 'coluna in catalogo.schema.tabela.coluna')"
        )
    child, parent, key = match.group("child"), match.group("parent"), match.group("key")
    return _normalize(f"""
        SELECT
          count_if(pai.{key} IS NULL) AS numerator,
          count(*) AS denominator,
          slice(array_agg(CASE WHEN pai.{key} IS NULL THEN to_json(struct(filho.{child})) END),
                1, {SAMPLE_LIMIT}) AS sample
        FROM {contract.asset} filho
        LEFT JOIN {parent} pai ON filho.{child} = pai.{key}
    """)


def _volume(rule: Rule, contract: Contract) -> str:
    return _normalize(f"""
        SELECT
          count(*) AS numerator,
          count(*) AS denominator,
          array(to_json(struct(count(*) AS linhas))) AS sample
        FROM {contract.asset}
    """)


def _freshness(rule: Rule, contract: Contract) -> str:
    return _normalize(f"""
        SELECT
          max(timestamp) AS ultima_escrita,
          unix_timestamp(current_timestamp()) - unix_timestamp(max(timestamp)) AS atraso_s
        FROM (DESCRIBE HISTORY {contract.asset})
    """)


def _required_expression(rule: Rule) -> str:
    if not rule.expression.strip():
        raise RuleCompilationError(f"regra {rule.rule_id} ({rule.dimension}) exige expression")
    return rule.expression.strip()


def _normalize(sql: str) -> str:
    return " ".join(sql.split())


VOLUME_MIN_HISTORY = 3


def evaluate_freshness(rule: Rule, delay_seconds: int) -> tuple[str, str]:
    """Compara o atraso da última escrita com o limite declarado no contrato."""
    limite = parse_duration_seconds(rule.threshold.lstrip("<=").strip())
    if delay_seconds <= limite:
        return PASSED, f"última escrita há {delay_seconds}s (limite {rule.threshold})"
    return VIOLATED, f"sem escrita há {delay_seconds}s, acima do limite {rule.threshold}"


def evaluate_volume(rule: Rule, current: int, history: list[int]) -> tuple[str, str]:
    """Compara a contagem atual com a mediana das contagens recentes."""
    if len(history) < VOLUME_MIN_HISTORY:
        return PASSED, f"histórico insuficiente ({len(history)} medições)"
    mediana = _median(history)
    if mediana == 0:
        return PASSED, "mediana histórica zerada"
    razao = current / mediana
    minimo = float(THRESHOLD_RE.match(rule.threshold.strip()).group("value"))
    if razao >= minimo:
        return PASSED, f"{current} linhas, {razao:.0%} da mediana ({mediana})"
    return VIOLATED, f"{current} linhas, apenas {razao:.0%} da mediana histórica ({mediana})"


def evaluate_schema(
    columns: list[ColumnSpec], actual: dict[str, str]
) -> tuple[str, str]:
    """Colunas ausentes ou com tipo divergente quebram o contrato; novas só informam."""
    if not columns:
        return PASSED, "contrato não declara colunas"
    ausentes = missing_columns(columns, actual)
    divergentes = type_mismatches(columns, actual)
    novas = undeclared_columns(columns, actual)

    if ausentes or divergentes:
        partes = []
        if ausentes:
            partes.append(f"colunas ausentes: {', '.join(ausentes)}")
        if divergentes:
            partes.append(f"tipos divergentes: {'; '.join(divergentes)}")
        return VIOLATED, " | ".join(partes)

    if novas:
        return PASSED, f"colunas novas não declaradas (compatível): {', '.join(novas)}"
    return PASSED, "schema conforme o contrato"


def _median(values: list[int]) -> float:
    ordenados = sorted(values)
    meio = len(ordenados) // 2
    if len(ordenados) % 2 == 1:
        return float(ordenados[meio])
    return (ordenados[meio - 1] + ordenados[meio]) / 2
