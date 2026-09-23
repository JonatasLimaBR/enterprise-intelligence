"""Quem depende do ativo que quebrou, e o quanto isso pesa.

A travessia procura o **melhor** caminho até cada nó, não o mais curto. Um salto por
aresta incerta vale 0,20; dois saltos por arestas confirmadas valem 0,25 — parar na
primeira visita subestimaria o impacto exatamente quando o atalho é o duvidoso.

Domínio puro: recebe arestas prontas e não sabe que Databricks existe (ADR-010).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from eict.domain import severity as severity_rules
from eict.domain.models import stable_id

POLICY_VERSION = "impact-rules-v1"

DOWNSTREAM = "downstream"
UPSTREAM = "upstream"
DEFAULT_MAX_DEPTH = 3

DECAY_PER_HOP = 0.5
WEIGHT_CONFIRMED_EDGE = 1.0
WEIGHT_UNCERTAIN_EDGE = 0.4
RECENCY_FULL_DAYS = 7
RECENCY_HORIZON_DAYS = 90
RECENCY_FLOOR = 0.3
WEIGHT_ENVIRONMENT = 1.0

CRITICALITY = {"DASHBOARD_V3": 1.0, "DASHBOARD": 1.0, "PIPELINE": 0.8, "JOB": 0.7, "": 0.5}
DEFAULT_CRITICALITY = 0.6

HUMAN_CONSUMPTION = ("DASHBOARD_V3", "DASHBOARD")


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    entity_type: str
    entity_id: str
    last_seen: datetime

    @property
    def is_uncertain(self) -> bool:
        """`entity_type` vazio: o lineage viu o caminho mas não quem o percorre."""
        return not self.entity_type

    @property
    def is_anonymous(self) -> bool:
        """Sem alvo e sem entidade: a aresta não diz quem consome, então não é consumidor.

        O lineage emite linhas assim; deixá-las passar criava um nó `desconhecido/` que
        inflava o raio sem informar nada.
        """
        return not self.target and not self.entity_id

    @property
    def node(self) -> str:
        """O destino: a tabela quando existe, senão a entidade que consome."""
        if self.target:
            return self.target
        return f"{self.entity_type or 'desconhecido'}/{self.entity_id}"

    @property
    def edge_id(self) -> str:
        return stable_id("edge", self.source, self.target, self.entity_type, self.entity_id)


@dataclass(frozen=True)
class ImpactNode:
    asset: str
    depth: int
    score: float
    uncertain: bool
    entity_type: str
    via_edge_id: str

    @property
    def is_human_consumption(self) -> bool:
        return self.entity_type in HUMAN_CONSUMPTION


@dataclass(frozen=True)
class ImpactResult:
    nodes: tuple[ImpactNode, ...] = ()
    policy_version: str = POLICY_VERSION

    @property
    def score(self) -> float:
        return round(sum(node.score for node in self.nodes), 4)

    @property
    def assets(self) -> tuple[str, ...]:
        return tuple(sorted(node.asset for node in self.nodes))

    @property
    def uncertain_assets(self) -> tuple[str, ...]:
        return tuple(sorted(node.asset for node in self.nodes if node.uncertain))


@dataclass(frozen=True)
class Escalation:
    from_severity: str
    to_severity: str
    asset: str
    edge_id: str
    reason: str


def recency_weight(edge: Edge, now: datetime) -> float:
    """Aresta recente conta inteira; aresta velha conta menos, mas nunca zero."""
    idade_dias = max((now - edge.last_seen).total_seconds() / 86_400, 0.0)
    if idade_dias <= RECENCY_FULL_DAYS:
        return 1.0
    if idade_dias >= RECENCY_HORIZON_DAYS:
        return RECENCY_FLOOR
    faixa = RECENCY_HORIZON_DAYS - RECENCY_FULL_DAYS
    andado = (idade_dias - RECENCY_FULL_DAYS) / faixa
    return 1.0 - andado * (1.0 - RECENCY_FLOOR)


def edge_weight(edge: Edge, now: datetime) -> float:
    """Recência × confiança × criticidade × ambiente.

    O fator de ambiente é 1,0 e inerte: neste workspace tudo roda em `dev`, então ele
    existe mas nunca discrimina. Fica visível em vez de omitido.
    """
    confianca = WEIGHT_UNCERTAIN_EDGE if edge.is_uncertain else WEIGHT_CONFIRMED_EDGE
    criticidade = CRITICALITY.get(edge.entity_type, DEFAULT_CRITICALITY)
    return recency_weight(edge, now) * confianca * criticidade * WEIGHT_ENVIRONMENT


def is_excluded(asset: str, excluded: tuple[str, ...]) -> bool:
    """Nome exato ou sufixo. Os sufixos de ruído são constantes do nosso próprio cenário."""
    return any(asset == item or asset.endswith(item) for item in excluded if item)


def traverse(
    edges: tuple[Edge, ...],
    origin: str,
    now: datetime,
    direction: str = DOWNSTREAM,
    max_depth: int = DEFAULT_MAX_DEPTH,
    excluded: tuple[str, ...] = (),
) -> ImpactResult:
    """Melhor caminho por nó, com reenfileiramento só quando o score cresce.

    Termina por dois motivos independentes: `max_depth` limita a profundidade, e um nó
    só volta à fila quando seu score aumenta estritamente — e o score é limitado por 1.
    O grafo real contém ciclo (`orders → orders_contract_backup → orders`), então isso
    não é precaução teórica.
    """
    if not edges or not origin or max_depth <= 0:
        return ImpactResult()

    adjacency = _adjacency(edges, direction, excluded)
    best: dict[str, ImpactNode] = {}
    fila: deque[tuple[str, int, float]] = deque([(origin, 0, 1.0)])

    while fila:
        atual, depth, score = fila.popleft()
        if depth >= max_depth:
            continue
        for edge in adjacency.get(atual, ()):
            destino = _destination(edge, direction)
            if destino == origin or is_excluded(destino, excluded):
                continue
            candidato = score * edge_weight(edge, now) * DECAY_PER_HOP
            anterior = best.get(destino)
            if anterior is not None and anterior.score >= candidato:
                continue
            best[destino] = ImpactNode(
                asset=destino,
                depth=depth + 1,
                score=round(candidato, 6),
                uncertain=edge.is_uncertain,
                entity_type=edge.entity_type,
                via_edge_id=edge.edge_id,
            )
            fila.append((destino, depth + 1, candidato))

    return ImpactResult(nodes=tuple(best[chave] for chave in sorted(best)))


def escalation(current_severity: str, result: ImpactResult) -> Escalation | None:
    """Só consumo humano eleva, e nunca até `blocking`.

    Aresta inferida não trava pipeline: apenas regra marcada `blocking` no contrato
    bloqueia (ADR-005, ADR-007).
    """
    if severity_rules.is_at_or_above(current_severity, severity_rules.CEILING):
        return None
    gatilhos = [node for node in result.nodes if node.is_human_consumption]
    if not gatilhos:
        return None
    culpado = max(gatilhos, key=lambda node: (node.score, node.asset))
    return Escalation(
        from_severity=current_severity,
        to_severity=severity_rules.CEILING,
        asset=culpado.asset,
        edge_id=culpado.via_edge_id,
        reason=(
            f"raio atinge consumo humano em {culpado.asset} "
            f"a {culpado.depth} salto(s), peso {culpado.score:.3f}"
        ),
    )


def changed_sources(result: ImpactResult, changed: frozenset[str]) -> tuple[str, ...]:
    """Ativos da travessia upstream cuja impressão digital de schema mudou."""
    return tuple(sorted(node.asset for node in result.nodes if node.asset in changed))


def _adjacency(
    edges: tuple[Edge, ...], direction: str, excluded: tuple[str, ...]
) -> dict[str, tuple[Edge, ...]]:
    agrupado: dict[str, list[Edge]] = {}
    for edge in edges:
        if edge.is_anonymous:
            continue
        chave = edge.source if direction == DOWNSTREAM else edge.node
        if is_excluded(chave, excluded):
            continue
        agrupado.setdefault(chave, []).append(edge)
    return {chave: tuple(itens) for chave, itens in agrupado.items()}


def _destination(edge: Edge, direction: str) -> str:
    return edge.node if direction == DOWNSTREAM else edge.source
