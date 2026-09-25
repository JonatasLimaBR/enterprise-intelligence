"""Conhecimento operacional: casos anteriores, eficácia dos runbooks e o que um problema ensinou.

Tudo aqui é explicável: o semelhante diz por que foi escolhido, a eficácia mostra quantos usos
sustentam o número, e o conhecimento cita o problema de onde veio. A atualização de runbook é só
sugestão — o YAML muda por PR, com revisão humana.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from eict.domain.models import stable_id

SIMILAR_LIMIT = 5
SIMILAR_WINDOW = timedelta(days=90)
EFFICACY_WINDOW = timedelta(hours=24)
MIN_CONFIDENT_USES = 5

_ATIVOS = frozenset({"detected", "triaged", "investigating", "mitigating", "monitoring"})

SUCESSO = "sucesso"
FALHA = "falha"
PENDENTE = "pendente"


# --- semelhantes --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Similar:
    incident_id: str
    similar_id: str
    level: int
    reason: str
    subject: str
    state: str
    hours_to_recover: float | None
    rank: int = 0


def similar(
    incident: dict,
    candidates: list[dict],
    causes: dict[str, str],
    now: datetime,
) -> list[Similar]:
    """Até 5 casos anteriores, do mais parecido ao menos: mesmo problema, mesma causa, mesmo sintoma."""
    causa = causes.get(incident["incident_id"])
    niveis: list[tuple[int, str, dict]] = []
    for outro in candidates:
        if outro["incident_id"] == incident["incident_id"] or outro["type"] != incident["type"]:
            continue
        if now - outro["detected_at"] > SIMILAR_WINDOW:
            continue
        mesma_causa = causa is not None and causes.get(outro["incident_id"]) == causa
        mesmo_ativo = outro["subject"] == incident["subject"]
        if mesmo_ativo and mesma_causa:
            niveis.append((1, "mesmo problema neste ativo", outro))
        elif mesma_causa:
            niveis.append((2, f"mesma causa em {outro['subject'].split('.')[-1]}", outro))
        elif mesmo_ativo:
            niveis.append((3, "mesmo sintoma neste ativo", outro))
    niveis.sort(key=lambda item: (item[0], item[2]["state"] != "recovered", -item[2]["detected_at"].timestamp()))
    return [
        Similar(
            incident_id=incident["incident_id"],
            similar_id=outro["incident_id"],
            level=nivel,
            reason=motivo,
            subject=outro["subject"],
            state=outro["state"],
            hours_to_recover=_hours_to_recover(outro),
            rank=posicao,
        )
        for posicao, (nivel, motivo, outro) in enumerate(niveis[:SIMILAR_LIMIT], start=1)
    ]


def _hours_to_recover(incident: dict) -> float | None:
    if incident["state"] != "recovered":
        return None
    return round((incident["updated_at"] - incident["detected_at"]).total_seconds() / 3600, 2)


# --- eficácia -----------------------------------------------------------------------------------


def outcome(usage_at: datetime, incident: dict, now: datetime) -> tuple[str, float | None]:
    """Resultado de um uso de runbook e, no sucesso, as horas do uso até a recuperação."""
    estado = incident["state"]
    if estado == "recovered":
        horas = (incident["updated_at"] - usage_at).total_seconds() / 3600
        return (SUCESSO, round(horas, 2)) if horas <= EFFICACY_WINDOW.total_seconds() / 3600 else (FALHA, None)
    if estado in _ATIVOS:
        return (PENDENTE, None) if now - usage_at < EFFICACY_WINDOW else (FALHA, None)
    return FALHA, None   # closed / cancelled: fechar por decisão não é recuperar


@dataclass(frozen=True)
class Efficacy:
    runbook_id: str
    uses: int
    successes: int
    failures: int
    pending: int
    median_hours_to_recover: float | None

    @property
    def efficacy(self) -> float | None:
        decididos = self.successes + self.failures
        return self.successes / decididos if decididos else None

    @property
    def small_sample(self) -> bool:
        return (self.successes + self.failures) < MIN_CONFIDENT_USES


def efficacy(usages: list[dict], incidents: dict[str, dict], now: datetime) -> list[Efficacy]:
    """Por runbook. O mesmo runbook no mesmo incidente conta uma vez — o primeiro uso."""
    primeiros: dict[tuple[str, str], dict] = {}
    for uso in sorted(usages, key=lambda item: item["at"]):
        primeiros.setdefault((uso["runbook_id"], uso["incident_id"]), uso)
    por_runbook: dict[str, list[tuple[str, float | None]]] = {}
    for (runbook_id, incident_id), uso in primeiros.items():
        incidente = incidents.get(incident_id)
        if incidente is None:
            continue
        por_runbook.setdefault(runbook_id, []).append(outcome(uso["at"], incidente, now))
    saida = []
    for runbook_id, resultados in sorted(por_runbook.items()):
        horas = [valor for resultado, valor in resultados if resultado == SUCESSO and valor is not None]
        saida.append(
            Efficacy(
                runbook_id=runbook_id,
                uses=len(resultados),
                successes=sum(1 for resultado, _ in resultados if resultado == SUCESSO),
                failures=sum(1 for resultado, _ in resultados if resultado == FALHA),
                pending=sum(1 for resultado, _ in resultados if resultado == PENDENTE),
                median_hours_to_recover=round(statistics.median(horas), 2) if horas else None,
            )
        )
    return saida


# --- conhecimento -------------------------------------------------------------------------------


@dataclass(frozen=True)
class KnowledgeItem:
    knowledge_id: str
    problem_id: str
    signature: str
    runbook_id: str
    symptom: str
    cause: str
    known_error: str
    workaround: str
    fix_description: str
    suggestion: str


def knowledge_item(candidate: dict, record: dict, runbook_id: str) -> KnowledgeItem | None:
    """Só problema com eficácia comprovada vira conhecimento; o resto ainda é hipótese de correção."""
    if candidate.get("status") != "resolvido" or not record.get("fix_description"):
        return None
    tipo, ativo, causa = candidate["signature"].split("|", 2)
    sintoma = f"{tipo} em {ativo}"
    correcao = record["fix_description"]
    alvo = runbook_id or "um runbook novo para este tipo"
    sugestao = (
        f"Acrescentar a {alvo}: quando o sintoma for '{sintoma}' e a causa '{causa}', "
        f"a correção comprovada (30 dias sem reincidência) foi: {correcao}"
        + (f". Known error: {record['known_error']}" if record.get("known_error") else "")
        + (f". Workaround enquanto isso: {record['workaround']}" if record.get("workaround") else "")
        + "."
    )
    return KnowledgeItem(
        knowledge_id=stable_id("kn", candidate["problem_id"]),
        problem_id=candidate["problem_id"],
        signature=candidate["signature"],
        runbook_id=runbook_id,
        symptom=sintoma,
        cause=causa,
        known_error=record.get("known_error") or "",
        workaround=record.get("workaround") or "",
        fix_description=correcao,
        suggestion=sugestao,
    )
