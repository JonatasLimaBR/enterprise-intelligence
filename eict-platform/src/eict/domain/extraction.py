"""Descobre como uma métrica é de fato calculada, lendo a árvore sintática do produtor.

Compara **valores, não tokens**. As métricas reais referenciam constantes de módulo
(`countDistinct(JOIN_KEY)`), e `JOIN_KEY` valer o mesmo nos dois arquivos é acidente, não
garantia. Sem resolver a constante, dois arquivos com chaves de join diferentes seriam
declarados equivalentes — e afirmar que dois números diferentes são o mesmo é pior do que
levantar um conflito falso.

`ast` é biblioteca padrão: o domínio segue sem saber que Databricks existe (ADR-010).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

EXTRAIDA = "extraida"
NAO_EXTRAIVEL = "nao_extraivel"
AMBIGUA = "ambigua"
PARCIAL = "parcial"

COMPARABLE = frozenset({EXTRAIDA, PARCIAL})
MAX_EXPANSION_DEPTH = 3
COLUMN_WRAPPERS = frozenset({"col", "column"})
FUNCTION_MODULES = frozenset({"F", "f", "sf", "func", "funcs", "functions"})


@dataclass(frozen=True)
class ObservedMetric:
    """Uma chamada de `.agg()` produz uma destas por métrica nomeada."""

    metric_id: str
    asset: str
    formula_raw: str
    formula_hash: str
    grain: tuple[str, ...]
    source_path: str
    source_line: int
    status: str
    detail: str = ""

    @property
    def is_comparable(self) -> bool:
        """`ambigua` e `nao_extraivel` nunca entram na comparação."""
        return self.status in COMPARABLE


def extract(source: str, path: str, asset: str) -> tuple[ObservedMetric, ...]:
    """Toda métrica nomeada num `.agg()`, com o grão do `groupBy` que a precede."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return (_unparseable(path, asset, f"arquivo não parseável: {exc}"),)

    constants = module_constants(tree)
    observed: list[ObservedMetric] = []
    for function in _functions(tree):
        bindings, ambiguous = column_bindings(function)
        for agg in _agg_calls(function):
            grain, grain_ok = _grain_of(agg)
            for metric_id, expression in _aliased(agg):
                observed.append(
                    _observe(
                        metric_id=metric_id,
                        expression=expression,
                        grain=grain,
                        grain_ok=grain_ok,
                        bindings=bindings,
                        ambiguous=ambiguous,
                        constants=constants,
                        path=path,
                        asset=asset,
                    )
                )
    return tuple(observed)


def module_constants(tree: ast.Module) -> dict[str, ast.expr]:
    """Atribuições de módulo a literais. É o que evita a falsa equivalência."""
    found: dict[str, ast.expr] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                found[target.id] = node.value
    return found


def column_bindings(function: ast.FunctionDef) -> tuple[dict[str, ast.expr], frozenset[str]]:
    """Ligações de `withColumn` no escopo, e os nomes ligados mais de uma vez.

    Um nome com duas ligações no mesmo escopo não pode ser substituído: a função tem
    ramos, e escolher um deles seria arbitrário. Esses nomes voltam como ambíguos.
    """
    bindings: dict[str, ast.expr] = {}
    seen_twice: set[str] = set()
    for node in ast.walk(function):
        if not _is_call_to(node, "withColumn") or len(node.args) < 2:
            continue
        name = _string_of(node.args[0])
        if name is None:
            continue
        if name in bindings and not _same_expression(bindings[name], node.args[1]):
            seen_twice.add(name)
        bindings[name] = node.args[1]
    return bindings, frozenset(seen_twice)


def normalize(
    expression: ast.expr,
    bindings: dict[str, ast.expr],
    constants: dict[str, ast.expr],
    depth: int = 0,
) -> ast.expr:
    """Forma canônica: constantes resolvidas, colunas desembrulhadas, ligações expandidas."""
    node = _substitute_names(expression, constants)
    node = _unwrap_columns(node)
    return _expand_bindings(node, bindings, constants, depth)


def formula_hash(expression: ast.expr) -> str:
    return ast.dump(expression, annotate_fields=False)


def unresolved_names(expression: ast.expr, constants: dict[str, ast.expr]) -> tuple[str, ...]:
    """Nomes que sobraram sem valor — a fórmula compara, mas não declara equivalência.

    O nome da função agregadora não conta: depois de desembrulhar, `F.sum(...)` vira
    `sum(...)` e `sum` é um `Name` em posição de chamada, não uma referência pendente.
    """
    chamadas = {
        node.func.id
        for node in ast.walk(expression)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    nomes = {
        node.id
        for node in ast.walk(expression)
        if isinstance(node, ast.Name)
        and node.id not in constants
        and node.id not in chamadas
        and node.id != "F"
    }
    return tuple(sorted(nomes))


def parse_expression(text: str) -> ast.expr | None:
    try:
        return ast.parse(text, mode="eval").body
    except SyntaxError:
        return None


def _observe(
    metric_id: str,
    expression: ast.expr,
    grain: tuple[str, ...],
    grain_ok: bool,
    bindings: dict[str, ast.expr],
    ambiguous: frozenset[str],
    constants: dict[str, ast.expr],
    path: str,
    asset: str,
) -> ObservedMetric:
    bruto = ast.unparse(expression)
    referenciados = _referenced_columns(expression, constants)
    if referenciados & ambiguous:
        return _with_status(
            metric_id, asset, bruto, "", grain, path, expression, AMBIGUA,
            f"coluna com mais de uma definição no escopo: {', '.join(sorted(referenciados & ambiguous))}",
        )
    if not grain_ok:
        return _with_status(
            metric_id, asset, bruto, "", grain, path, expression, NAO_EXTRAIVEL,
            "granularidade não é literal",
        )

    normalizada = normalize(expression, bindings, constants)
    pendentes = unresolved_names(normalizada, constants)
    status = PARCIAL if pendentes else EXTRAIDA
    detalhe = f"nomes não resolvidos: {', '.join(pendentes)}" if pendentes else ""
    return ObservedMetric(
        metric_id=metric_id,
        asset=asset,
        formula_raw=bruto,
        formula_hash=formula_hash(normalizada),
        grain=grain,
        source_path=path,
        source_line=getattr(expression, "lineno", 0),
        status=status,
        detail=detalhe,
    )


def _with_status(
    metric_id: str,
    asset: str,
    bruto: str,
    digest: str,
    grain: tuple[str, ...],
    path: str,
    expression: ast.expr,
    status: str,
    detail: str,
) -> ObservedMetric:
    return ObservedMetric(
        metric_id=metric_id,
        asset=asset,
        formula_raw=bruto,
        formula_hash=digest,
        grain=grain,
        source_path=path,
        source_line=getattr(expression, "lineno", 0),
        status=status,
        detail=detail,
    )


def _unparseable(path: str, asset: str, detail: str) -> ObservedMetric:
    return ObservedMetric(
        metric_id="",
        asset=asset,
        formula_raw="",
        formula_hash="",
        grain=(),
        source_path=path,
        source_line=0,
        status=NAO_EXTRAIVEL,
        detail=detail,
    )


def _functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def _agg_calls(function: ast.FunctionDef) -> list[ast.Call]:
    return [node for node in ast.walk(function) if _is_call_to(node, "agg")]


def _grain_of(agg: ast.Call) -> tuple[tuple[str, ...], bool]:
    """O `groupBy` que precede o `agg` na mesma cadeia."""
    node = agg.func.value if isinstance(agg.func, ast.Attribute) else None
    while isinstance(node, ast.Call):
        if _is_call_to(node, "groupBy"):
            colunas = [_string_of(arg) for arg in node.args]
            if any(nome is None for nome in colunas) or node.keywords:
                return (), False
            return tuple(nome for nome in colunas if nome), True
        node = node.func.value if isinstance(node.func, ast.Attribute) else None
    return (), True


def _aliased(agg: ast.Call) -> list[tuple[str, ast.expr]]:
    """Cada `.alias("nome")` dentro do `agg` é uma métrica nomeada."""
    saida: list[tuple[str, ast.expr]] = []
    for arg in agg.args:
        if not _is_call_to(arg, "alias") or not arg.args:
            continue
        nome = _string_of(arg.args[0])
        if nome and isinstance(arg.func, ast.Attribute):
            saida.append((nome, arg.func.value))
    return saida


def _substitute_names(expression: ast.expr, constants: dict[str, ast.expr]) -> ast.expr:
    class _Troca(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.expr:
            alvo = constants.get(node.id)
            return ast.copy_location(_clone(alvo), node) if alvo is not None else node

    return _Troca().visit(_clone(expression))


def _unwrap_columns(expression: ast.expr) -> ast.expr:
    """`F.col("x")` e `"x"` são a mesma coluna; `F.sum(...)` vira `sum(...)`.

    O receptor só é descartado quando é o módulo de funções. Em `F.row_number().over(w)`
    o receptor **é** o significado: descartá-lo tornaria `max(row_number().over(w))` e
    `max(sum(x).over(w))` indistinguíveis — uma falsa equivalência entre métricas que
    calculam coisas diferentes.
    """

    class _Despe(ast.NodeTransformer):
        def visit_Call(self, node: ast.Call) -> ast.expr:
            self.generic_visit(node)
            if not isinstance(node.func, ast.Attribute):
                return node
            if node.func.attr in COLUMN_WRAPPERS and len(node.args) == 1:
                return node.args[0]
            receptor = node.func.value
            argumentos = (
                list(node.args)
                if _is_functions_module(receptor)
                else [receptor, *node.args]
            )
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id=node.func.attr, ctx=ast.Load()),
                    args=argumentos,
                    keywords=node.keywords,
                ),
                node,
            )

    return ast.fix_missing_locations(_Despe().visit(_clone(expression)))


def _is_functions_module(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id in FUNCTION_MODULES


def _expand_bindings(
    expression: ast.expr,
    bindings: dict[str, ast.expr],
    constants: dict[str, ast.expr],
    depth: int,
) -> ast.expr:
    """Uma coluna criada por `withColumn` é substituída pela expressão que a criou."""
    if depth >= MAX_EXPANSION_DEPTH or not bindings:
        return expression

    trocou = False

    class _Expande(ast.NodeTransformer):
        def visit_Constant(self, node: ast.Constant) -> ast.expr:
            nonlocal trocou
            alvo = bindings.get(node.value) if isinstance(node.value, str) else None
            if alvo is None:
                return node
            trocou = True
            interno = _unwrap_columns(_substitute_names(alvo, constants))
            return ast.copy_location(interno, node)

    resultado = ast.fix_missing_locations(_Expande().visit(_clone(expression)))
    if not trocou:
        return resultado
    return _expand_bindings(resultado, bindings, constants, depth + 1)


def _referenced_columns(expression: ast.expr, constants: dict[str, ast.expr]) -> set[str]:
    resolvida = _unwrap_columns(_substitute_names(expression, constants))
    return {
        node.value
        for node in ast.walk(resolvida)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _is_call_to(node: ast.AST, attribute: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    )


def _string_of(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _same_expression(left: ast.expr, right: ast.expr) -> bool:
    return ast.dump(left, annotate_fields=False) == ast.dump(right, annotate_fields=False)


def _clone(node: ast.expr) -> ast.expr:
    return ast.parse(ast.unparse(node), mode="eval").body
