from __future__ import annotations

import json
from datetime import datetime

from eict.domain.models import Evidence, RuleResult
from eict.domain.severity import rank_of

EVIDENCE_KIND = "rule_violation"
ERROR_KIND = "rule_evaluation_error"
DEFAULT_SEVERITY = "warning"


def latest_per_rule(results: list[RuleResult]) -> list[RuleResult]:
    """Só a avaliação mais recente de cada regra conta.

    Os resultados são carregados numa janela de horas para tolerar um ciclo em que a
    etapa de qualidade não rodou. Sem esta redução, uma violação já corrigida continua
    somando: um incidente aberto depois do conserto nascia com a severidade de um
    problema que não existe mais.
    """
    mais_recente: dict[tuple[str, str], RuleResult] = {}
    for result in results:
        chave = (result.asset, result.rule_id)
        atual = mais_recente.get(chave)
        if atual is None or result.evaluated_at > atual.evaluated_at:
            mais_recente[chave] = result
    return list(mais_recente.values())


def group_violations(results: list[RuleResult]) -> dict[str, list[RuleResult]]:
    """Agrupa violações por ativo: N regras quebradas no mesmo contrato = 1 incidente."""
    grouped: dict[str, list[RuleResult]] = {}
    for result in results:
        if result.is_violation:
            grouped.setdefault(result.asset, []).append(result)
    return {asset: sorted(items, key=lambda item: item.rule_id) for asset, items in grouped.items()}


def group_errors(results: list[RuleResult]) -> dict[str, list[RuleResult]]:
    grouped: dict[str, list[RuleResult]] = {}
    for result in results:
        if result.is_error:
            grouped.setdefault(result.asset, []).append(result)
    return grouped


def incident_severity(results: list[RuleResult]) -> str:
    """A severidade do incidente é a mais alta entre as regras quebradas."""
    if not results:
        return DEFAULT_SEVERITY
    return max(results, key=lambda item: rank_of(item.severity)).severity


def first_result_id(results: list[RuleResult]) -> str:
    return min(results, key=lambda item: (item.evaluated_at, item.rule_id)).result_id


def build_evidence(result: RuleResult, now: datetime) -> Evidence:
    """A evidência carrega o que permite agir sem abrir notebook."""
    payload = {
        "rule_id": result.rule_id,
        "dimension": result.dimension,
        "threshold": result.threshold,
        "severity": result.severity,
        "window": result.window,
        "query_hash": result.query_hash,
        "numerator": result.numerator,
        "denominator": result.denominator,
        "sample": list(result.sample),
    }
    return Evidence.create(
        kind=EVIDENCE_KIND,
        source_ref=f"rule/{result.contract_id}/{result.rule_id}",
        observed_at=now,
        summary=result.summary(),
        value=json.dumps(payload, ensure_ascii=False, default=str),
    )


def build_error_evidence(result: RuleResult, now: datetime) -> Evidence:
    return Evidence.create(
        kind=ERROR_KIND,
        source_ref=f"rule/{result.contract_id}/{result.rule_id}",
        observed_at=now,
        summary=result.summary(),
        value=result.error_message,
    )


def violation_summary(asset: str, results: list[RuleResult]) -> str:
    dimensoes = ", ".join(sorted({result.dimension for result in results}))
    bloqueantes = [result for result in results if result.is_blocking]
    texto = f"{len(results)} regra(s) violada(s) em {asset} ({dimensoes})"
    if bloqueantes:
        texto += f"; {len(bloqueantes)} bloqueante(s)"
    return texto


def has_blocking(results: list[RuleResult]) -> bool:
    return any(result.is_blocking for result in results)
