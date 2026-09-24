from __future__ import annotations

import functools
import json
import os
import uuid
from datetime import UTC, datetime

import streamlit as st
from acceptance import IDENTITY_HEADER, refusal, statements
from access import ACCEPT_REGIME, REVIEW_HYPOTHESIS, VIEW_AUDIT, authorize, can, load_directory
from audit import ADULTERADA, BIFURCADA, entry, verify
from databricks import sql
from databricks.sdk.core import Config

CATALOG = os.getenv("EICT_CATALOG", "workspace")
SCHEMA_PREFIX = os.getenv("EICT_SCHEMA_PREFIX", "eict_")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
NOT_AVAILABLE = "not_available"

st.set_page_config(page_title="EICT - Incidentes", layout="wide")


def table(layer: str, name: str) -> str:
    return f"{CATALOG}.{SCHEMA_PREFIX}{layer}.{name}"


def connection():
    config = Config()
    return sql.connect(
        server_hostname=config.host.replace("https://", ""),
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: config.authenticate,
    )


def query(statement: str, parameters: dict | None = None) -> list[dict]:
    with connection() as connection_handle, connection_handle.cursor() as cursor:
        cursor.execute(statement, parameters or {})
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def execute(statement: str, parameters: dict) -> None:
    with connection() as connection_handle, connection_handle.cursor() as cursor:
        cursor.execute(statement, parameters)


@st.cache_data(ttl=60)
def load_incidents() -> list[dict]:
    return query(
        f"SELECT * FROM {table('ops', 'incidents')} ORDER BY updated_at DESC LIMIT 50"
    )


def load_timeline(incident_id: str) -> list[dict]:
    return query(
        f"SELECT at, kind, summary, actor FROM {table('ops', 'incident_timeline')} "
        "WHERE incident_id = :incident_id ORDER BY at",
        {"incident_id": incident_id},
    )


def load_hypotheses(incident_id: str) -> list[dict]:
    return query(
        f"SELECT * FROM {table('ops', 'hypotheses')} "
        "WHERE incident_id = :incident_id ORDER BY rank",
        {"incident_id": incident_id},
    )


def load_evidence(incident_id: str) -> dict[str, dict]:
    rows = query(
        f"SELECT * FROM {table('ops', 'evidence')} WHERE incident_id = :incident_id",
        {"incident_id": incident_id},
    )
    return {row["evidence_id"]: row for row in rows}


def load_narrative(incident_id: str) -> dict | None:
    rows = query(
        f"SELECT * FROM {table('ops', 'narratives')} "
        "WHERE incident_id = :incident_id ORDER BY created_at DESC LIMIT 1",
        {"incident_id": incident_id},
    )
    return rows[0] if rows else None


def load_run_features(run_ids: list[str]) -> dict[str, dict]:
    if not run_ids:
        return {}
    quoted = ", ".join(f"'{run_id}'" for run_id in run_ids)
    rows = query(f"SELECT * FROM {table('gold', 'run_features')} WHERE run_id IN ({quoted})")
    return {row["run_id"]: row for row in rows}


def load_cost(run_id: str) -> dict | None:
    rows = query(
        f"SELECT * FROM {table('ops', 'run_cost')} WHERE run_id = :run_id",
        {"run_id": run_id},
    )
    return rows[0] if rows else None


def load_rule_results(asset: str) -> list[dict]:
    return query(
        f"SELECT * FROM {table('ops', 'rule_results')} "
        "WHERE asset = :asset ORDER BY evaluated_at DESC, rule_id LIMIT 20",
        {"asset": asset},
    )


def render_rule_results(results: list[dict]) -> None:
    if not results:
        st.caption("Nenhum resultado de regra registrado para este ativo.")
        return
    rotulos = {"violated": "violada", "passed": "ok", "evaluation_error": "erro de execução"}
    linhas = [
        {
            "regra": item["rule_id"],
            "dimensão": item["dimension"],
            "estado": rotulos.get(item["status"], item["status"]),
            "resultado": _resultado(item),
            "limite": item["threshold"],
            "severidade": item["severity"],
        }
        for item in results
    ]
    st.dataframe(linhas, use_container_width=True, hide_index=True)

    bloqueantes = [item for item in results if item["status"] == "violated" and item["severity"] == "blocking"]
    if bloqueantes:
        st.error(f"{len(bloqueantes)} violação(ões) bloqueante(s): avise os consumidores antes do próximo deploy.")

    erros = [item for item in results if item["status"] == "evaluation_error"]
    if erros:
        st.warning(
            f"{len(erros)} regra(s) não puderam ser avaliadas — isso é falha do motor, não dado ruim."
        )


def _resultado(item: dict) -> str:
    if item["status"] == "evaluation_error":
        return (item.get("error_message") or "")[:80]
    if item.get("denominator"):
        return f"{item['numerator']} de {item['denominator']} ({item['ratio']:.2%})"
    return str(item.get("numerator", ""))


def load_reviews(incident_id: str) -> list[dict]:
    return query(
        f"SELECT * FROM {table('ops', 'hypothesis_reviews')} "
        "WHERE incident_id = :incident_id ORDER BY at DESC",
        {"incident_id": incident_id},
    )


def save_review(incident_id: str, hypothesis_id: str, decision: str, reviewer: str, note: str) -> None:
    execute(
        f"INSERT INTO {table('ops', 'hypothesis_reviews')} "
        "(review_id, hypothesis_id, incident_id, decision, reviewer, at, note) "
        "VALUES (:review_id, :hypothesis_id, :incident_id, :decision, :reviewer, :at, :note)",
        {
            "review_id": str(uuid.uuid4()),
            "hypothesis_id": hypothesis_id,
            "incident_id": incident_id,
            "decision": decision,
            "reviewer": reviewer,
            "at": datetime.now(UTC),
            "note": note,
        },
    )


def render_diff(healthy: dict | None, current: dict) -> None:
    dimensions = [
        ("commit", "git_sha"),
        ("ambiente", "env_hash"),
        ("execução (s) — decide a regressão", "execution_s"),
        ("setup do ambiente (s)", "setup_s"),
        ("duração total (s)", "duration_s"),
        ("linhas de entrada", "input_rows"),
        ("maior chave (linhas)", "max_key_rows"),
        ("mediana (linhas)", "median_key_rows"),
        ("skew ratio", "skew_ratio"),
        ("share da chave quente", "top_key_share"),
        ("operadores do plano", "plan_operators"),
    ]
    rows = []
    for label, column in dimensions:
        healthy_value = _render(healthy.get(column)) if healthy else NOT_AVAILABLE
        current_value = _render(current.get(column))
        rows.append(
            {
                "dimensão": label,
                "run saudável": healthy_value,
                "run atual": current_value,
                "mudou": _changed(healthy_value, current_value),
            }
        )
    rows.append({"dimensão": "spill", "run saudável": NOT_AVAILABLE, "run atual": NOT_AVAILABLE, "mudou": ""})
    rows.append({"dimensão": "GC", "run saudável": NOT_AVAILABLE, "run atual": NOT_AVAILABLE, "mudou": ""})
    st.dataframe(rows, use_container_width=True, hide_index=True)


@st.cache_resource
def directory():
    return load_directory()


def identity() -> str | None:
    """Sempre o cabeçalho do Databricks Apps: nunca um e-mail digitado."""
    return st.context.headers.get(IDENTITY_HEADER)


def append_audit(decision, target: str) -> None:
    """Grava a decisão na trilha, encadeada à última linha. Vem antes da escrita de negócio."""
    ultima = query(
        f"SELECT seq, hash FROM {table('ops', 'audit_log')} ORDER BY seq DESC, audit_id DESC LIMIT 1"
    )
    linha = entry(
        ultima[0] if ultima else None,
        datetime.now(UTC),
        decision.actor,
        decision.roles,
        decision.action,
        target,
        "allowed" if decision.allowed else "denied",
        decision.reason,
    )
    execute(
        f"INSERT INTO {table('ops', 'audit_log')} "
        "(seq, audit_id, at, actor, identity_source, roles, action, target, decision, reason, prev_hash, hash) "
        "VALUES (:seq, :audit_id, :at, :actor, :identity_source, :roles, :action, :target, :decision, "
        ":reason, :prev_hash, :hash)",
        linha,
    )


def guarded(action: str, target: str, run) -> bool:
    """Autoriza, audita (permitido ou negado) e só então age."""
    decision = authorize(directory(), identity(), action)
    append_audit(decision, target)
    if not decision.allowed:
        st.error(f"Ação negada: {decision.reason}")
        return False
    run()
    return True


def render_audit() -> None:
    st.title("Auditoria")
    st.caption("Decisões humanas no console, permitidas e negadas. Trilha append-only com cadeia de hash.")
    rows = query(f"SELECT * FROM {table('ops', 'audit_log')} ORDER BY seq, audit_id")
    veredito = verify(rows)
    if veredito.status == ADULTERADA:
        st.error(f"Trilha adulterada — {veredito.detail}")
    elif veredito.status == BIFURCADA:
        st.warning(f"Trilha íntegra com escritas concorrentes nas linhas {sorted(set(veredito.forks))}")
    else:
        st.success(f"Trilha íntegra · {len(rows)} registro(s)")
    st.dataframe(
        [
            {campo: row[campo] for campo in ("seq", "at", "actor", "roles", "action", "target", "decision", "reason")}
            for row in reversed(rows)
        ],
        use_container_width=True,
        hide_index=True,
    )


def accept_regime(incident: dict, email: str, reason: str) -> None:
    """Aceita o nível atual como novo normal: regime, incidente fechado e timeline."""
    first = query(
        f"SELECT start_time FROM {table('gold', 'run_features')} WHERE run_id = :run_id",
        {"run_id": incident["first_run_id"]},
    )
    if not first:
        raise ValueError("primeiro run do incidente não encontrado em run_features")
    now = datetime.now(UTC)
    for statement, parameters in statements(incident, first[0]["start_time"], email, reason, now, table):
        execute(statement, parameters)
    load_incidents.clear()


def render_acceptance(incident: dict) -> None:
    with st.expander("Aceitar como novo normal"):
        st.caption(
            "Use quando a mudança é intencional. O baseline recomeça no primeiro run deste "
            "incidente e o incidente é fechado como decisão, registrando quem aceitou e por quê."
        )
        email = identity()
        reason = st.text_area("Justificativa", key=f"regime-{incident['incident_id']}")
        recusa = refusal(email, reason)
        st.caption(f"Identidade: {email}" if email else "Identidade não encaminhada.")
        if st.button("Aceitar regime", key=f"accept-{incident['incident_id']}", disabled=recusa is not None):
            if guarded(ACCEPT_REGIME, incident["incident_id"], lambda: accept_regime(incident, email, reason)):
                st.rerun()
        if recusa and (reason or not email):
            st.caption(recusa)


def _changed(healthy_value: str, current_value: str) -> str:
    if NOT_AVAILABLE in (healthy_value, current_value):
        return ""
    return "sim" if healthy_value != current_value else ""


def _render(value) -> str:
    if value is None or value == "":
        return NOT_AVAILABLE
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or NOT_AVAILABLE
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


usuario = identity()
papeis = directory().roles_of(usuario)
st.sidebar.caption(
    f"{usuario or 'identidade não encaminhada'} · "
    + (", ".join(sorted(papeis)) if papeis else "só leitura")
)
if directory().error:
    st.sidebar.warning(directory().error)
visoes = ["Incidentes"] + (["Auditoria"] if can(directory(), usuario, VIEW_AUDIT) else [])
if st.sidebar.radio("Visão", visoes) == "Auditoria":
    render_audit()
    st.stop()

st.title("EICT - Control Tower")
st.caption("Incidentes correlacionados com evidência, impacto e custo")

incidents = load_incidents()
if not incidents:
    st.info("Nenhum incidente registrado ainda.")
    st.stop()

labels = {
    f"{incident['subject']} · {incident['state']} · {incident['detected_at']:%d/%m %H:%M}": incident
    for incident in incidents
}
selected_label = st.sidebar.radio("Incidentes", list(labels))
incident = labels[selected_label]

header = st.columns(4)
header[0].metric("Incidente", incident["incident_id"][:12])
header[1].metric("Estado", incident["state"])
header[2].metric(
    "Severidade",
    incident["severity"],
    help=(
        f"elevada de {incident['escalated_from']}: {incident['escalation_reason']}"
        if incident.get("escalated_from")
        else None
    ),
)
cost = load_cost(incident["last_run_id"])
header[3].metric(
    "Custo incremental",
    NOT_AVAILABLE if not cost or cost["status"] != "available" else f"US$ {cost['incremental_cost_usd']:.2f}",
    help=None if not cost else f"status: {cost['status']}",
)

raio = incident.get("affected_assets") or []
if raio:
    score = incident.get("impact_score") or 0.0
    st.caption(
        f"**Raio de impacto** · score {score:.3f} · {len(raio)} ativo(s) atingido(s)"
        + (f" · elevada de `{incident['escalated_from']}`" if incident.get("escalated_from") else "")
    )
    st.write(", ".join(f"`{item}`" for item in raio))

narrative = load_narrative(incident["incident_id"])
evidence = load_evidence(incident["incident_id"])
st.subheader("Resumo")
if narrative:
    sentences = json.loads(narrative["sentences_json"])
    for sentence in sentences:
        citations = ", ".join(sentence["evidence_ids"])
        st.markdown(f"- {sentence['text']}  \n  <small>evidências: {citations}</small>", unsafe_allow_html=True)
    origem = "LLM" if narrative["source"] == "llm" else "determinístico (fallback)"
    reason = narrative["rejected_reason"]
    st.caption(f"Origem: {origem}" + (f" · motivo: {reason}" if reason else ""))
else:
    st.caption("Narrativa ainda não gerada.")

if incident["type"] == "runtime_regression":
    st.subheader("Comparação de runs")
    features = load_run_features([incident["first_run_id"], incident["last_run_id"]])
    current = features.get(incident["last_run_id"], {})
    healthy_rows = query(
        f"SELECT * FROM {table('gold', 'run_features')} "
        "WHERE job_id = :job_id AND result_state = 'SUCCESS' AND end_time < :before "
        "ORDER BY end_time DESC LIMIT 1",
        {"job_id": incident["subject"], "before": incident["detected_at"]},
    )
    render_diff(healthy_rows[0] if healthy_rows else None, current)
    ativo = incident["state"] in ("detected", "triaged", "investigating", "mitigating", "monitoring")
    if ativo and can(directory(), usuario, ACCEPT_REGIME):
        render_acceptance(incident)
else:
    st.subheader("Regras violadas")
    render_rule_results(load_rule_results(incident["subject"]))

st.subheader("Hipóteses")
reviews = {review["hypothesis_id"]: review for review in load_reviews(incident["incident_id"])}
for hypothesis in load_hypotheses(incident["incident_id"]):
    review = reviews.get(hypothesis["hypothesis_id"])
    status = review["decision"] if review else hypothesis["status"]
    with st.expander(
        f"#{hypothesis['rank']} · {hypothesis['statement']} · confiança {hypothesis['confidence']:.2f} · {status}",
        expanded=hypothesis["rank"] == 1,
    ):
        for bucket, title in (("supporting", "A favor"), ("contradicting", "Contra"), ("missing", "Ausente")):
            ids = hypothesis.get(bucket) or []
            if not ids:
                continue
            st.markdown(f"**{title}**")
            for evidence_id in ids:
                item = evidence.get(evidence_id)
                st.markdown(f"- `{evidence_id}` {item['summary'] if item else NOT_AVAILABLE}")
        if status not in ("confirmed", "rejected") and can(directory(), usuario, REVIEW_HYPOTHESIS):
            hyp_id = hypothesis["hypothesis_id"]
            note = st.text_input("Nota", key=f"note-{hyp_id}")
            columns = st.columns(2)
            botoes = ((columns[0], "Confirmar causa", "confirmed"), (columns[1], "Descartar", "rejected"))
            for coluna, rotulo, decisao in botoes:
                if not coluna.button(rotulo, key=f"{decisao}-{hyp_id}"):
                    continue
                gravar = functools.partial(
                    save_review, incident["incident_id"], hyp_id, decisao, usuario, note
                )
                if guarded(REVIEW_HYPOTHESIS, hyp_id, gravar):
                    st.rerun()

st.subheader("Impacto")
descobertos = list(incident.get("affected_assets") or [])
declarados = list(incident.get("declared_consumers") or [])
colunas = st.columns(2)
colunas[0].markdown("**Descobertos (lineage)**")
colunas[0].write(", ".join(descobertos) if descobertos else NOT_AVAILABLE)
colunas[1].markdown("**Declarados (contrato)**")
colunas[1].write(", ".join(declarados) if declarados else NOT_AVAILABLE)

nao_declarados = sorted(set(descobertos) - set(declarados))
nao_vistos = sorted(set(declarados) - set(descobertos))
if nao_declarados:
    st.warning(f"Consumo não governado (fora do contrato): {', '.join(nao_declarados)}")
if nao_vistos:
    st.info(f"Declarado no contrato mas não visto no lineage: {', '.join(nao_vistos)}")

tickets = incident.get("ticket_refs") or []
st.subheader("Ticket")
st.write(tickets[0] if tickets else NOT_AVAILABLE)

st.subheader("Timeline")
st.dataframe(load_timeline(incident["incident_id"]), use_container_width=True, hide_index=True)
