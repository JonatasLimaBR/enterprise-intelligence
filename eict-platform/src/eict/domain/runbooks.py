"""Runbooks versionados e a escolha do runbook para cada incidente.

O runbook diz a que se aplica: tipos de incidente, causas (códigos de hipótese) e, para violação
de contrato, dimensões da regra. A escolha é explicável — cada runbook aplicável vem com o motivo.
Rascunho aparece, com aviso, depois dos aprovados: um procedimento não revisado não pode passar
por um que foi.
"""

from __future__ import annotations

from dataclasses import dataclass

APROVADO = "aprovado"
RASCUNHO = "rascunho"
STATUSES = frozenset({APROVADO, RASCUNHO})

NIVEL_CAUSA = 1
NIVEL_TIPO = 2
NO_HYPOTHESIS = "sem_hipotese"  # o mesmo valor de problems.NO_HYPOTHESIS


class RunbookError(ValueError):
    """Runbook inválido: recusado inteiro, os demais seguem."""


@dataclass(frozen=True)
class Runbook:
    runbook_id: str
    title: str
    status: str
    owner: str
    incident_types: tuple[str, ...]
    hypothesis_codes: tuple[str, ...]
    dimensions: tuple[str, ...]
    steps: tuple[str, ...]
    connector: bool = False
    source_file: str = ""

    @property
    def has_trigger(self) -> bool:
        return bool(self.incident_types) or self.connector


@dataclass(frozen=True)
class Applicable:
    runbook: Runbook
    level: int
    reason: str


def parse(payload: object, source: str = "") -> Runbook:
    if not isinstance(payload, dict):
        raise RunbookError(f"{source}: conteúdo não é um mapeamento")
    obrigatorios = ("runbook_id", "title", "status", "owner")
    faltando = [campo for campo in obrigatorios if not str(payload.get(campo) or "").strip()]
    if faltando:
        raise RunbookError(f"{source}: campos obrigatórios ausentes: {', '.join(faltando)}")
    if payload["status"] not in STATUSES:
        raise RunbookError(f"{source}: status '{payload['status']}' inválido (use {', '.join(sorted(STATUSES))})")
    alvo = payload.get("applies_to")
    if not isinstance(alvo, dict) or "incident_types" not in alvo:
        raise RunbookError(f"{source}: `applies_to.incident_types` é obrigatório (lista, pode ser vazia)")
    passos = payload.get("steps")
    if not isinstance(passos, list) or not [passo for passo in passos if str(passo).strip()]:
        raise RunbookError(f"{source}: `steps` precisa de ao menos um passo")
    return Runbook(
        runbook_id=str(payload["runbook_id"]).strip(),
        title=str(payload["title"]).strip(),
        status=payload["status"],
        owner=str(payload["owner"]).strip(),
        incident_types=tuple(alvo.get("incident_types") or ()),
        hypothesis_codes=tuple(alvo.get("hypothesis_codes") or ()),
        dimensions=tuple(alvo.get("dimensions") or ()),
        steps=tuple(str(passo).strip() for passo in passos if str(passo).strip()),
        connector=bool(alvo.get("connector", False)),
        source_file=source,
    )


def applicable(
    runbooks: list[Runbook], incident_type: str, cause: str, dimensions: frozenset[str] = frozenset()
) -> list[Applicable]:
    """Runbooks do incidente, do mais específico ao mais geral; aprovado antes de rascunho.

    A restrição do runbook só vale quando o incidente **tem** a informação restringida. Um
    `sla_risk` não tem hipótese nem dimensão: casa pelo tipo com o runbook de freshness. Uma
    violação de schema tem dimensão: o runbook de freshness, que restringe a `freshness`, não serve.
    """
    causa_conhecida = bool(cause) and cause != NO_HYPOTHESIS
    saida: list[Applicable] = []
    for runbook in runbooks:
        if incident_type not in runbook.incident_types:
            continue
        if runbook.hypothesis_codes and causa_conhecida and cause in runbook.hypothesis_codes:
            saida.append(Applicable(runbook, NIVEL_CAUSA, "tipo e causa"))
        elif runbook.dimensions and dimensions and dimensions & set(runbook.dimensions):
            saida.append(Applicable(runbook, NIVEL_CAUSA, "tipo e dimensão"))
        elif (runbook.hypothesis_codes and causa_conhecida) or (runbook.dimensions and dimensions):
            continue  # o runbook restringe algo que o incidente tem, e não casou
        else:
            saida.append(Applicable(runbook, NIVEL_TIPO, "tipo"))
    return sorted(saida, key=lambda item: (item.level, item.runbook.status != APROVADO, item.runbook.runbook_id))
