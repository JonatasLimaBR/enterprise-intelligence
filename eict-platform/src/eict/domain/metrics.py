"""O que a métrica deveria ser, e o que o código diz que ela é.

O produto desta camada é a **divergência**. Uma definição declarada sozinha é documentação;
uma extraída sozinha é arqueologia. A diferença entre as duas é o que alguém precisa decidir.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError, field_validator

from eict.domain.extraction import (
    ObservedMetric,
    formula_hash,
    normalize,
    parse_expression,
)

CANONICAL = "canonical"
PROPOSED = "proposed"
STATUSES = frozenset({CANONICAL, PROPOSED})

FORMULA_CONFLICT = "formula_conflict"
GRAIN_CONFLICT = "grain_conflict"
SYNONYM = "synonym"
DECLARED_NOT_COMPUTED = "declared_not_computed"
COMPUTED_NOT_DECLARED = "computed_not_declared"
DECLARED_MISMATCH = "declared_mismatch"

BLOCKING_DIVERGENCES = frozenset({FORMULA_CONFLICT, GRAIN_CONFLICT, DECLARED_MISMATCH})


class MetricError(ValueError):
    """Declaração malformada: a métrica inteira é recusada."""


class MetricDeclaration(BaseModel):
    metric_id: str = Field(min_length=1)
    asset: str = Field(min_length=1)
    formula: str = Field(min_length=1)
    grain: list[str] = Field(min_length=1)
    owner: str = Field(min_length=1)
    status: str
    version: str = Field(min_length=1)
    dimensions: list[str] = Field(default_factory=list)
    currency: str = ""
    calendar: str = ""
    examples: list[str] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def known_status(cls, value: str) -> str:
        if value not in STATUSES:
            raise ValueError(f"status inválido: {value} (use {sorted(STATUSES)})")
        return value

    @property
    def is_canonical(self) -> bool:
        """Proposta não é verdade: só o dono promove a definição (PRD-020)."""
        return self.status == CANONICAL

    @property
    def formula_hash(self) -> str:
        expression = normalize_declared(self.formula)
        return formula_hash(expression) if expression is not None else ""


@dataclass(frozen=True)
class Divergence:
    kind: str
    metric_id: str
    asset: str
    detail: str
    left: str = ""
    right: str = ""

    @property
    def is_blocking(self) -> bool:
        return self.kind in BLOCKING_DIVERGENCES


def normalize_declared(text: str) -> ast.expr | None:
    """A fórmula declarada usa colunas como nomes nus; o código as usa como strings.

    `sum(amount * (1 - discount_pct / 100))` e `F.sum(F.col("net_amount"))` expandido
    precisam chegar à mesma forma, senão toda declaração correta viraria divergência.
    """
    expression = parse_expression(text)
    if expression is None:
        return None
    chamadas = {
        node.func.id
        for node in ast.walk(expression)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    class _ColunasComoTexto(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.expr:
            if node.id in chamadas:
                return node
            return ast.copy_location(ast.Constant(value=node.id), node)

    convertida = ast.fix_missing_locations(_ColunasComoTexto().visit(expression))
    return normalize(convertida, {}, {})


def parse_declaration(payload: dict) -> MetricDeclaration:
    try:
        return MetricDeclaration(**payload)
    except ValidationError as exc:
        raise MetricError(str(exc)) from exc


def compare(
    declarations: list[MetricDeclaration], observed: list[ObservedMetric]
) -> tuple[Divergence, ...]:
    """Toda forma de desacordo entre o declarado e o calculado."""
    comparaveis = [item for item in observed if item.is_comparable and item.metric_id]
    canonicas = {
        (item.asset, item.metric_id): item for item in declarations if item.is_canonical
    }
    return (
        *_formula_conflicts(comparaveis),
        *_grain_conflicts(comparaveis),
        *_synonyms(comparaveis),
        *_declared_not_computed(canonicas, comparaveis),
        *_computed_not_declared(canonicas, comparaveis),
        *_declared_mismatch(canonicas, comparaveis),
    )


def _by_metric(observed: list[ObservedMetric]) -> dict[tuple[str, str], list[ObservedMetric]]:
    agrupado: dict[tuple[str, str], list[ObservedMetric]] = {}
    for item in observed:
        agrupado.setdefault((item.asset, item.metric_id), []).append(item)
    return agrupado


def _formula_conflicts(observed: list[ObservedMetric]) -> list[Divergence]:
    saida = []
    for (asset, metric_id), itens in sorted(_by_metric(observed).items()):
        hashes = {item.formula_hash for item in itens}
        if len(hashes) < 2:
            continue
        ordenados = sorted(itens, key=lambda item: (item.source_path, item.source_line))
        saida.append(
            Divergence(
                kind=FORMULA_CONFLICT,
                metric_id=metric_id,
                asset=asset,
                detail=(
                    f"{len(hashes)} fórmulas para o mesmo nome: "
                    + " | ".join(
                        f"{item.source_path}:{item.source_line} → {item.formula_raw}"
                        for item in ordenados
                    )
                ),
                left=ordenados[0].formula_raw,
                right=ordenados[-1].formula_raw,
            )
        )
    return saida


def _grain_conflicts(observed: list[ObservedMetric]) -> list[Divergence]:
    saida = []
    for (asset, metric_id), itens in sorted(_by_metric(observed).items()):
        graos = {item.grain for item in itens}
        if len(graos) < 2:
            continue
        ordenados = sorted(graos)
        saida.append(
            Divergence(
                kind=GRAIN_CONFLICT,
                metric_id=metric_id,
                asset=asset,
                detail="granularidades diferentes: "
                + " | ".join("(" + ", ".join(grao) + ")" for grao in ordenados),
                left=", ".join(ordenados[0]),
                right=", ".join(ordenados[-1]),
            )
        )
    return saida


def _synonyms(observed: list[ObservedMetric]) -> list[Divergence]:
    """Fórmulas idênticas sob nomes diferentes no mesmo ativo."""
    por_formula: dict[tuple[str, str], set[str]] = {}
    for item in observed:
        if item.formula_hash:
            por_formula.setdefault((item.asset, item.formula_hash), set()).add(item.metric_id)
    saida = []
    for (asset, _), nomes in sorted(por_formula.items()):
        if len(nomes) < 2:
            continue
        ordenados = sorted(nomes)
        saida.append(
            Divergence(
                kind=SYNONYM,
                metric_id=ordenados[0],
                asset=asset,
                detail=f"mesma fórmula sob nomes diferentes: {', '.join(ordenados)}",
                left=ordenados[0],
                right=ordenados[-1],
            )
        )
    return saida


def _declared_not_computed(
    canonicas: dict[tuple[str, str], MetricDeclaration], observed: list[ObservedMetric]
) -> list[Divergence]:
    calculadas = {(item.asset, item.metric_id) for item in observed}
    return [
        Divergence(
            kind=DECLARED_NOT_COMPUTED,
            metric_id=metric_id,
            asset=asset,
            detail=f"declarada por {declaracao.owner}, mas nenhum código a calcula",
        )
        for (asset, metric_id), declaracao in sorted(canonicas.items())
        if (asset, metric_id) not in calculadas
    ]


def _computed_not_declared(
    canonicas: dict[tuple[str, str], MetricDeclaration], observed: list[ObservedMetric]
) -> list[Divergence]:
    vistos: set[tuple[str, str]] = set()
    saida = []
    for item in sorted(observed, key=lambda obs: (obs.asset, obs.metric_id)):
        chave = (item.asset, item.metric_id)
        if chave in canonicas or chave in vistos:
            continue
        vistos.add(chave)
        saida.append(
            Divergence(
                kind=COMPUTED_NOT_DECLARED,
                metric_id=item.metric_id,
                asset=item.asset,
                detail=f"calculada em {item.source_path}:{item.source_line}, sem declaração",
                left=item.formula_raw,
            )
        )
    return saida


def _declared_mismatch(
    canonicas: dict[tuple[str, str], MetricDeclaration], observed: list[ObservedMetric]
) -> list[Divergence]:
    saida = []
    for (asset, metric_id), declaracao in sorted(canonicas.items()):
        itens = [
            item
            for item in observed
            if item.asset == asset and item.metric_id == metric_id and item.formula_hash
        ]
        esperado = declaracao.formula_hash
        if not itens or not esperado:
            continue
        if any(item.formula_hash == esperado for item in itens):
            continue
        saida.append(
            Divergence(
                kind=DECLARED_MISMATCH,
                metric_id=metric_id,
                asset=asset,
                detail=(
                    f"nenhuma implementação corresponde à declaração de {declaracao.owner}: "
                    f"declarado `{declaracao.formula}`, encontrado "
                    + " | ".join(sorted({item.formula_raw for item in itens}))
                ),
                left=declaracao.formula,
                right=itens[0].formula_raw,
            )
        )
    return saida
