"""As relações entre os ativos, com a origem de cada afirmação.

Só entram relações que têm fonte neste workspace. `serves`, `deployed_as` e
`supports_process` ficam de fora: não há processos de negócio nem deployments modelados, e
uma aresta que ninguém pode confirmar nem contradizer não é conhecimento — é decoração.

Inferência nunca sobrescreve fato confirmado (ADR-003): quando as duas fontes divergem, a
`asserted` prevalece e a `discovered` é preservada como aresta concorrente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from eict.domain.models import stable_id

PRODUCES = "produces"
CONSUMES = "consumes"
OWNED_BY = "owned_by"
IMPLEMENTS_METRIC = "implements_metric"
CONTAINS_SENSITIVE_DATA = "contains_sensitive_data"

SUPPORTED_PREDICATES = frozenset(
    {PRODUCES, CONSUMES, OWNED_BY, IMPLEMENTS_METRIC, CONTAINS_SENSITIVE_DATA}
)
UNSUPPORTED_PREDICATES = frozenset({"serves", "deployed_as", "supports_process"})

ASSERTED = "asserted"
DISCOVERED = "discovered"
INFERRED = "inferred"
STATUS_RANK = {INFERRED: 0, DISCOVERED: 1, ASSERTED: 2}

CONFIDENCE_ASSERTED = 1.0
CONFIDENCE_DISCOVERED = 0.85
SENSITIVE_CLASSIFICATIONS = frozenset({"restricted", "confidential", "pii"})


@dataclass(frozen=True)
class OntologyEdge:
    subject: str
    predicate: str
    object: str
    origin: str
    status: str
    confidence: float
    observed_at: datetime

    @property
    def edge_id(self) -> str:
        return stable_id("ont", self.subject, self.predicate, self.object)

    @property
    def rank(self) -> int:
        return STATUS_RANK.get(self.status, 0)


def from_lineage(edges: list, now: datetime) -> list[OntologyEdge]:
    """Cada aresta do grafo materializado vira `produces` e o seu inverso `consumes`."""
    saida: list[OntologyEdge] = []
    for edge in edges:
        destino = getattr(edge, "node", "")
        origem = getattr(edge, "source", "")
        if not origem or not destino:
            continue
        saida.append(_edge(origem, PRODUCES, destino, "lineage", DISCOVERED, now))
        saida.append(_edge(destino, CONSUMES, origem, "lineage", DISCOVERED, now))
    return saida


def from_contracts(contracts: list, now: datetime) -> list[OntologyEdge]:
    saida: list[OntologyEdge] = []
    for contract in contracts:
        asset = getattr(contract, "asset", "")
        if not asset:
            continue
        produtor = getattr(contract, "producer", "")
        if produtor:
            saida.append(_edge(produtor, PRODUCES, asset, "contract", ASSERTED, now))
        dono = getattr(contract, "owner", "")
        if dono:
            saida.append(_edge(asset, OWNED_BY, dono, "contract", ASSERTED, now))
        for consumidor in getattr(contract, "consumers", ()) or ():
            saida.append(_edge(consumidor, CONSUMES, asset, "contract", ASSERTED, now))
        if getattr(contract, "classification", "") in SENSITIVE_CLASSIFICATIONS:
            saida.append(
                _edge(asset, CONTAINS_SENSITIVE_DATA, contract.classification,
                      "contract", ASSERTED, now)
            )
    return saida


def from_metrics(declarations: list, now: datetime) -> list[OntologyEdge]:
    return [
        _edge(item.asset, IMPLEMENTS_METRIC, item.metric_id, "metric_registry", ASSERTED, now)
        for item in declarations
        if getattr(item, "is_canonical", False)
    ]


def merge(*groups: list[OntologyEdge]) -> tuple[OntologyEdge, ...]:
    """Mesma tripla vinda de fontes diferentes: a afirmada vence, sem apagar a descoberta.

    A aresta concorrente é preservada porque a divergência entre o declarado e o observado
    é informação — é o mesmo princípio que faz o registry de métricas existir.
    """
    melhor: dict[tuple[str, str, str], OntologyEdge] = {}
    concorrentes: list[OntologyEdge] = []
    for grupo in groups:
        for edge in grupo:
            chave = (edge.subject, edge.predicate, edge.object)
            atual = melhor.get(chave)
            if atual is None:
                melhor[chave] = edge
            elif edge.rank > atual.rank:
                melhor[chave] = edge
                concorrentes.append(atual)
            elif edge.origin != atual.origin:
                concorrentes.append(edge)
    ordenadas = sorted(
        [*melhor.values(), *concorrentes],
        key=lambda item: (item.subject, item.predicate, item.object, -item.rank),
    )
    return tuple(ordenadas)


def _edge(
    subject: str, predicate: str, obj: str, origin: str, status: str, now: datetime
) -> OntologyEdge:
    return OntologyEdge(
        subject=subject,
        predicate=predicate,
        object=obj,
        origin=origin,
        status=status,
        confidence=CONFIDENCE_ASSERTED if status == ASSERTED else CONFIDENCE_DISCOVERED,
        observed_at=now,
    )
