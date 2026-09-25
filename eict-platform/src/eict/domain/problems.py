"""Gestão de problemas: incidente que se repete vira problema, e problema só fecha provando que parou.

- **Assinatura** = tipo + ativo/job + hipótese nº 1. O mesmo sintoma pela mesma causa. Causas
  diferentes no mesmo ativo são problemas diferentes.
- **Candidato** com 3 ou mais incidentes da assinatura em 30 dias; uma pessoa promove a problema.
- **Eficácia** (PRD-010 E5): registrada a correção, o problema fica em observação; 30 dias sem
  reincidência o resolvem; reincidência o marca ineficaz. Job verde não prova correção.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from eict.domain.models import stable_id

WINDOW = timedelta(days=30)
MIN_INCIDENTS = 3
EFFICACY_WINDOW = timedelta(days=30)
POLICY_VERSION = "problems-v1"

NO_HYPOTHESIS = "sem_hipotese"

CANDIDATO = "candidato"
ABERTO = "aberto"
EM_OBSERVACAO = "em_observacao"
RESOLVIDO = "resolvido"
INEFICAZ = "ineficaz"


def top_cause(hypotheses: list[dict]) -> str:
    """Hipótese de menor rank que não foi descartada por revisão."""
    viaveis = sorted(
        (item for item in hypotheses if item.get("status") != "rejected"),
        key=lambda item: int(item.get("rank") or 99),
    )
    return viaveis[0]["code"] if viaveis else NO_HYPOTHESIS


def signature(incident: dict, cause: str) -> str:
    return f"{incident['type']}|{incident['subject']}|{cause}"


def problem_id(sig: str) -> str:
    return stable_id("prb", sig)


@dataclass(frozen=True)
class Candidate:
    problem_id: str
    signature: str
    type: str
    subject: str
    cause: str
    incident_ids: tuple[str, ...]
    first_detected_at: datetime
    last_detected_at: datetime
    impact_score_sum: float
    open_hours: float
    status: str
    efficacy_detail: str = ""

    @property
    def incident_count(self) -> int:
        return len(self.incident_ids)


def efficacy(fix_at: datetime | None, incidents: list[dict], now: datetime) -> tuple[str, str]:
    """Estado derivado da correção registrada. Sem correção, o problema está aberto."""
    if fix_at is None:
        return ABERTO, ""
    reincidentes = sorted(
        (item for item in incidents if item["detected_at"] > fix_at),
        key=lambda item: item["detected_at"],
    )
    if reincidentes:
        primeiro = reincidentes[0]
        return INEFICAZ, (
            f"reincidiu em {primeiro['detected_at']:%Y-%m-%d %H:%M} UTC ({primeiro['incident_id']}), "
            f"depois da correção de {fix_at:%Y-%m-%d}"
        )
    if now - fix_at >= EFFICACY_WINDOW:
        return RESOLVIDO, f"{EFFICACY_WINDOW.days} dias sem reincidência desde a correção"
    faltam = (EFFICACY_WINDOW - (now - fix_at)).days
    return EM_OBSERVACAO, f"sem reincidência até agora; faltam {faltam} dia(s) de observação"


def build(
    incidents: list[dict],
    hypotheses_by_incident: dict[str, list[dict]],
    records: dict[str, dict],
    now: datetime,
) -> list[Candidate]:
    """Candidatos (≥ 3 na janela) e problemas já promovidos, cada um com o estado derivado.

    Um problema promovido continua acompanhado mesmo abaixo do mínimo: é justamente quando a
    recorrência cai que a eficácia precisa ser medida.
    """
    grupos: dict[str, list[dict]] = {}
    causas: dict[str, str] = {}
    for incidente in incidents:
        causa = top_cause(hypotheses_by_incident.get(incidente["incident_id"], []))
        sig = signature(incidente, causa)
        grupos.setdefault(sig, []).append(incidente)
        causas[sig] = causa

    saida: list[Candidate] = []
    for sig, itens in grupos.items():
        pid = problem_id(sig)
        registro = records.get(pid)
        na_janela = [item for item in itens if item["detected_at"] >= now - WINDOW]
        if registro is None and len(na_janela) < MIN_INCIDENTS:
            continue
        considerados = itens if registro is not None else na_janela
        if registro is None:
            status, detalhe = CANDIDATO, f"{len(na_janela)} incidentes em {WINDOW.days} dias"
        else:
            status, detalhe = efficacy(registro.get("fix_at"), itens, now)
        tipo, sujeito, _ = sig.split("|", 2)
        saida.append(
            Candidate(
                problem_id=pid,
                signature=sig,
                type=tipo,
                subject=sujeito,
                cause=causas[sig],
                incident_ids=tuple(
                    item["incident_id"] for item in sorted(considerados, key=lambda i: i["detected_at"])
                ),
                first_detected_at=min(item["detected_at"] for item in considerados),
                last_detected_at=max(item["detected_at"] for item in considerados),
                impact_score_sum=round(sum(float(item.get("impact_score") or 0.0) for item in considerados), 4),
                open_hours=round(sum(_open_hours(item, now) for item in considerados), 2),
                status=status,
                efficacy_detail=detalhe,
            )
        )
    return sorted(saida, key=lambda item: (-item.incident_count, item.signature))


_ACTIVE = frozenset({"detected", "triaged", "investigating", "mitigating", "monitoring"})


def _open_hours(incident: dict, now: datetime) -> float:
    """Ativo conta até agora; fechado, até o fechamento."""
    fim = now if incident.get("state") in _ACTIVE else (incident.get("updated_at") or now)
    return max(0.0, (fim - incident["detected_at"]).total_seconds() / 3600)


def row(candidate: Candidate, now: datetime) -> dict:
    return {
        "problem_id": candidate.problem_id,
        "signature": candidate.signature,
        "type": candidate.type,
        "subject": candidate.subject,
        "cause": candidate.cause,
        "incident_ids": list(candidate.incident_ids),
        "incident_count": candidate.incident_count,
        "first_detected_at": candidate.first_detected_at,
        "last_detected_at": candidate.last_detected_at,
        "impact_score_sum": candidate.impact_score_sum,
        "open_hours": candidate.open_hours,
        "status": candidate.status,
        "efficacy_detail": candidate.efficacy_detail,
        "policy_version": POLICY_VERSION,
        "evaluated_at": now,
    }
