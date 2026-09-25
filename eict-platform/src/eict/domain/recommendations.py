"""Recomendações read-only: o que verificar e o que fazer — nunca executado pela plataforma.

Regras que vêm do PRD-000 e da SPEC-004:

- **Read-only.** Nenhuma remediação automática; a recomendação diz, uma pessoa decide.
- **Separar fato, inferência e recomendação.** Cada recomendação cita a hipótese de que parte e
  as evidências dela, e diz se a causa é inferida ou confirmada por revisão.
- **Recomendar testes, não só ações** (SPEC-004, passo 10): primeiro como confirmar, depois o que
  fazer. Com hipótese fraca, a recomendação é coletar a evidência que falta — agir sobre palpite
  é pior que não recomendar.
"""

from __future__ import annotations

from dataclasses import dataclass

from eict.domain.models import stable_id

POLICY_VERSION = "recommendations-v2"  # v2: limiar 0.7
MIN_CONFIDENCE = 0.7  # validado pelo dono do produto em 2026-09-24 (era 0.5)

VERIFY = "verificar"
ACT = "agir"
COLLECT = "coletar_evidencia"

CONFIRMED = "confirmed"
REJECTED = "rejected"


@dataclass(frozen=True)
class Playbook:
    verify: str
    act: str
    owner_role: str = "engenheiro_dados"


CATALOG: dict[str, Playbook] = {
    "skew_join_change": Playbook(
        verify="Compare o plano do run lento com o do último saudável e a distribuição da chave do join "
        "(linhas da chave mais frequente sobre a mediana).",
        act="Trate a chave quente: salting ou broadcast do lado menor, ou reverta o commit que mudou o join.",
    ),
    "code_change": Playbook(
        verify="Leia o diff do commit citado nos arquivos do produtor e rode o job no commit anterior "
        "para comparar o resultado.",
        act="Reverta ou corrija o commit; se a mudança é intencional, aceite o novo regime no console.",
    ),
    "compute_change": Playbook(
        verify="Compare o env_hash e a configuração de compute do run lento com a do saudável.",
        act="Restaure a configuração anterior de compute ou ajuste a nova; registre se for intencional.",
        owner_role="operador",
    ),
    "volume_growth": Playbook(
        verify="Confirme o crescimento da entrada na origem (contagem por dia) e se é sazonal ou permanente.",
        act="Se o volume novo é permanente, aceite o novo regime; se não, investigue a origem da carga extra.",
    ),
    "pipeline_failure": Playbook(
        verify="Veja o último run do produtor: terminou com sucesso dentro da janela do SLO?",
        act="Reexecute o produtor e trate a causa da falha antes do próximo prazo.",
        owner_role="operador",
    ),
    "upstream_change": Playbook(
        verify="Compare o schema atual da tabela de origem com o declarado no contrato.",
        act="Alinhe o produtor à origem ou negocie a mudança com o dono da origem; avise os consumidores.",
        owner_role="data_steward",
    ),
    "data_source_quality": Playbook(
        verify="Rode a mesma regra direto na origem para confirmar que o dado já chega violado.",
        act="Abra a correção com o dono da origem; enquanto isso, sinalize o dado aos consumidores.",
        owner_role="data_steward",
    ),
    "change_temporal_only": Playbook(
        verify="Nada na evidência identifica o autor: liste as mudanças da janela e descarte uma a uma.",
        act="Sem ação recomendada até uma hipótese específica ganhar evidência.",
    ),
}

BY_INCIDENT_TYPE: dict[str, Playbook] = {
    "sla_risk": Playbook(
        verify="Confira se o produtor está rodando e quanto falta para o prazo (evidência do incidente).",
        act="Dispare o produtor agora; se não couber no prazo, avise os consumidores antes que estoure.",
        owner_role="operador",
    ),
    "cost_regression": Playbook(
        verify="Compare o env_hash e o performance_target do run caro com os do baseline.",
        act="Volte à classe de compute anterior ou aceite o custo novo se a mudança for deliberada.",
    ),
    "semantic_conflict": Playbook(
        verify="Compare as duas fórmulas citadas na evidência com a definição canônica da métrica.",
        act="Alinhe o código à definição canônica ou atualize a definição com o dono da métrica.",
        owner_role="data_steward",
    ),
    "quality_engine_failure": Playbook(
        verify="Leia o erro de execução da regra: é a regra, o acesso ou a tabela?",
        act="Corrija a regra no contrato ou o acesso do job; não é defeito do dado.",
    ),
}


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: str
    incident_id: str
    hypothesis_id: str
    kind: str
    text: str
    basis: str                 # "inferida (confiança 0.90)" | "confirmada por revisão" | "tipo do incidente"
    evidence_ids: tuple[str, ...]
    owner_role: str
    policy_version: str = POLICY_VERSION


def recommend(incident: dict, hypotheses: list[dict]) -> list[Recommendation]:
    """Recomendações do incidente: verificar e agir sobre a melhor hipótese viável.

    Hipótese descartada por revisão é ignorada; confirmada dispensa o limiar de confiança. Sem
    hipótese forte, recomenda coletar o que falta — citando o que a própria hipótese diz faltar.
    """
    candidatas = sorted(
        (item for item in hypotheses if item.get("status") != REJECTED and item.get("code") in CATALOG),
        key=lambda item: (item.get("status") != CONFIRMED, int(item.get("rank") or 99)),
    )
    if candidatas:
        topo = candidatas[0]
        confirmada = topo.get("status") == CONFIRMED
        confianca = float(topo.get("confidence") or 0.0)
        evidencias = tuple(topo.get("supporting") or ())
        if confirmada or confianca >= MIN_CONFIDENCE:
            playbook = CATALOG[topo["code"]]
            base = "confirmada por revisão" if confirmada else f"inferida (confiança {confianca:.2f})"
            return [
                _make(incident, topo["hypothesis_id"], VERIFY, playbook.verify, base, evidencias, playbook),
                _make(incident, topo["hypothesis_id"], ACT, playbook.act, base, evidencias, playbook),
            ]
        faltando = list(topo.get("missing") or ())
        texto = (
            "Hipótese mais forte ainda fraca "
            f"({topo.get('code')}, confiança {confianca:.2f}). Colete antes de agir: "
            + ("; ".join(faltando) if faltando else "evidência que confirme ou descarte a hipótese")
            + "."
        )
        return [
            _make(incident, topo["hypothesis_id"], COLLECT, texto, f"inferida (confiança {confianca:.2f})",
                  evidencias, CATALOG[topo["code"]])
        ]

    playbook = BY_INCIDENT_TYPE.get(incident.get("type", ""))
    if playbook is None:
        return []
    return [
        _make(incident, "", VERIFY, playbook.verify, "tipo do incidente", (), playbook),
        _make(incident, "", ACT, playbook.act, "tipo do incidente", (), playbook),
    ]


def _make(incident, hypothesis_id, kind, text, basis, evidence_ids, playbook) -> Recommendation:
    return Recommendation(
        recommendation_id=stable_id("rec", incident["incident_id"], hypothesis_id, kind, POLICY_VERSION),
        incident_id=incident["incident_id"],
        hypothesis_id=hypothesis_id,
        kind=kind,
        text=text,
        basis=basis,
        evidence_ids=tuple(evidence_ids),
        owner_role=playbook.owner_role,
    )


def acceptance_rate(reviews: list[dict]) -> tuple[float | None, int, int]:
    """Taxa de aceitas sobre decididas (PRD-000); pendentes não entram no denominador."""
    decididas = [item for item in reviews if item.get("decision") in ("accepted", "rejected")]
    aceitas = sum(1 for item in decididas if item["decision"] == "accepted")
    return (aceitas / len(decididas) if decididas else None), aceitas, len(decididas)
