from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from eict.domain.models import Evidence, Hypothesis, Incident

MAX_SENTENCES = 8
FALLBACK_SOURCE = "fallback"
LLM_SOURCE = "llm"


class Sentence(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(min_length=1)


class NarrativeModel(BaseModel):
    sentences: list[Sentence] = Field(min_length=1, max_length=MAX_SENTENCES)


@dataclass(frozen=True)
class Fact:
    evidence_id: str
    text: str


@dataclass(frozen=True)
class Narrative:
    source: str
    sentences: tuple[Sentence, ...]
    rejected_reason: str | None = None


def build_facts(evidence: list[Evidence]) -> tuple[Fact, ...]:
    return tuple(Fact(item.evidence_id, item.summary) for item in evidence)


def build_prompt(incident: Incident, hypotheses: list[Hypothesis], facts: tuple[Fact, ...]) -> str:
    fact_lines = "\n".join(f"- {fact.evidence_id}: {fact.text}" for fact in facts)
    hypothesis_lines = "\n".join(
        f"- #{hypothesis.rank} ({hypothesis.confidence:.2f}) {hypothesis.statement}"
        for hypothesis in sorted(hypotheses, key=lambda item: item.rank)
    )
    return (
        "Você resume incidentes de engenharia de dados em português do Brasil.\n"
        "Use apenas os fatos listados. Cada frase deve citar ao menos um evidence_id dos fatos.\n"
        "Nunca afirme uma causa como confirmada; hipóteses são hipóteses.\n"
        "Responda apenas com JSON no formato "
        '{"sentences": [{"text": "...", "evidence_ids": ["ev-..."]}]}.\n\n'
        f"Incidente: {incident.incident_id} (job {incident.job_id}, estado {incident.state})\n\n"
        f"Hipóteses ranqueadas:\n{hypothesis_lines}\n\n"
        f"Fatos disponíveis:\n{fact_lines}\n"
    )


def validate_narrative(
    raw: str, allowed_ids: set[str]
) -> tuple[NarrativeModel | None, str | None]:
    try:
        model = NarrativeModel.model_validate_json(_strip_fences(as_text(raw)))
    except ValidationError as exc:
        return None, f"schema:{exc.error_count()}"
    except ValueError:
        return None, "json_invalid"
    unknown = {
        evidence_id
        for sentence in model.sentences
        for evidence_id in sentence.evidence_ids
        if evidence_id not in allowed_ids
    }
    if unknown:
        return None, f"unknown_evidence:{','.join(sorted(unknown))}"
    return model, None


def fallback_narrative(
    incident: Incident, hypotheses: list[Hypothesis], facts: tuple[Fact, ...]
) -> Narrative:
    by_id = {fact.evidence_id: fact for fact in facts}
    ordered = sorted(hypotheses, key=lambda item: item.rank)
    sentences: list[Sentence] = []
    for hypothesis in ordered[:MAX_SENTENCES]:
        evidence_ids = [
            evidence_id for evidence_id in hypothesis.supporting if evidence_id in by_id
        ] or [evidence_id for evidence_id in hypothesis.contradicting if evidence_id in by_id]
        if not evidence_ids:
            continue
        details = "; ".join(by_id[evidence_id].text for evidence_id in evidence_ids[:2])
        sentences.append(
            Sentence(
                text=(
                    f"Hipótese #{hypothesis.rank} (confiança {hypothesis.confidence:.2f}): "
                    f"{hypothesis.statement}. Evidências: {details}."
                )[:400],
                evidence_ids=evidence_ids,
            )
        )
    if not sentences and facts:
        sentences.append(
            Sentence(text=f"Fatos observados: {facts[0].text}.", evidence_ids=[facts[0].evidence_id])
        )
    return Narrative(source=FALLBACK_SOURCE, sentences=tuple(sentences))


def narrate(
    raw: str | None,
    incident: Incident,
    hypotheses: list[Hypothesis],
    facts: tuple[Fact, ...],
) -> Narrative:
    allowed = {fact.evidence_id for fact in facts}
    if raw is None:
        return fallback_narrative(incident, hypotheses, facts)
    model, reason = validate_narrative(raw, allowed)
    if model is None:
        fallback = fallback_narrative(incident, hypotheses, facts)
        return Narrative(
            source=FALLBACK_SOURCE, sentences=fallback.sentences, rejected_reason=reason
        )
    return Narrative(source=LLM_SOURCE, sentences=tuple(model.sentences))


def as_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "") if isinstance(part, dict) else getattr(part, "text", "")
            for part in content
        ]
        return "".join(part for part in parts if isinstance(part, str))
    return str(content)


def _strip_fences(text: str) -> str:
    stripped = as_text(text).strip()
    if stripped.startswith("```"):
        lines = [line for line in stripped.split("\n")[1:] if line.strip() != "```"]
        stripped = "\n".join(lines)
    return stripped.strip()
