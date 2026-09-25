from __future__ import annotations

import functools
import json
import os
import uuid
from datetime import UTC, datetime

import streamlit as st
from acceptance import IDENTITY_HEADER, refusal, statements
from access import (
    ACCEPT_REGIME,
    ACKNOWLEDGE_INCIDENT,
    APPROVE_SAVING,
    DISCARD_SAVING,
    FOLLOW_RUNBOOK,
    IMPLEMENT_SAVING,
    MANAGE_PROBLEM,
    REVIEW_HYPOTHESIS,
    REVIEW_RECOMMENDATION,
    VIEW_AUDIT,
    authorize,
    can,
    load_directory,
)
from acknowledge import can_acknowledge
from acknowledge import statements as acknowledge_statements
from audit import ADULTERADA, BIFURCADA, entry, verify
from databricks import sql
from databricks.sdk.core import Config
from money import fmt_money, fmt_share
from savings_actions import SavingsActionError
from savings_actions import approve as approve_statements
from savings_actions import discard as discard_statements
from savings_actions import implement as implement_statements

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


CONFIANCA = {"alta": "confiança alta", "baixa": "amostra pequena", "sem_dados": "sem dados"}


def _valor(metrica: dict) -> str:
    if metrica["value"] is None:
        return "não medido"
    if metrica["unit"] == "US$":
        return f"US$ {metrica['value']:,.4f}"
    if metrica["unit"] == "horas":
        return f"{metrica['value']:.1f} h"
    if metrica["unit"] == "%":
        return f"{metrica['value']:.0f}%"
    return f"{metrica['value']:.0f}"


def render_executive() -> None:
    """DASH-01 (SPEC-017): cada número com janela, fonte, amostra, fórmula e confiança."""
    st.title("Resumo executivo")
    try:
        metricas = query(f"SELECT * FROM {table('ops', 'executive_summary')} ORDER BY metric_id")
    except Exception:
        st.info("O resumo é calculado pelo ciclo; aguardando o primeiro após a publicação.")
        return
    if not metricas:
        st.info("Resumo ainda não calculado.")
        return
    st.caption(f"Calculado em {metricas[0]['computed_at']:%d/%m %H:%M} UTC · {metricas[0]['policy_version']}")
    ordem = [
        "active_incidents", "critical_incidents", "sla_at_risk", "impacted_assets",
        "incremental_cost_usd", "mttr_hours", "mtta_hours", "administrative_closures", "unhealthy_connectors",
        "recommendations_accepted", "savings_identified_usd", "savings_approved_usd", "savings_realized_usd",
        "savings_realization_rate",
    ]
    por_id = {metrica["metric_id"]: metrica for metrica in metricas}
    colunas = st.columns(3)
    for posicao, metric_id in enumerate(item for item in ordem if item in por_id):
        metrica = por_id[metric_id]
        with colunas[posicao % 3]:
            st.metric(metrica["label"], _valor(metrica), help=f"{metrica['formula']} · fonte: {metrica['source']}")
            confianca = CONFIANCA.get(metrica["confidence"], metrica["confidence"])
            st.caption(
                f"{metrica['window']} · n={metrica['n']} · {confianca}"
                + (f" · {metrica['detail']}" if metrica["detail"] else "")
            )


ESTADO_PROBLEMA = {
    "candidato": "🟠 candidato",
    "aberto": "🔴 aberto",
    "em_observacao": "🟡 em observação",
    "resolvido": "🟢 resolvido",
    "ineficaz": "⛔ correção ineficaz",
}


def promote_problem(candidate: dict, owner: str, due_at, metric: str, known_error: str, workaround: str) -> None:
    execute(
        f"MERGE INTO {table('ops', 'problem_records')} t "
        "USING (SELECT :problem_id AS problem_id) s ON t.problem_id = s.problem_id "
        "WHEN NOT MATCHED THEN INSERT (problem_id, signature, owner, due_at, success_metric, known_error, "
        "workaround, fix_description, fix_at, promoted_by, promoted_at) VALUES (:problem_id, :signature, :owner, "
        ":due_at, :metric, :known_error, :workaround, NULL, NULL, :promoted_by, :now)",
        {
            "problem_id": candidate["problem_id"],
            "signature": candidate["signature"],
            "owner": owner,
            "due_at": due_at,
            "metric": metric,
            "known_error": known_error or None,
            "workaround": workaround or None,
            "promoted_by": usuario,
            "now": datetime.now(UTC),
        },
    )


def register_fix(problem_id: str, description: str) -> None:
    """A correção abre a janela de verificação de eficácia: 30 dias sem reincidência."""
    execute(
        f"UPDATE {table('ops', 'problem_records')} SET fix_description = :description, fix_at = :now "
        "WHERE problem_id = :problem_id",
        {"description": description, "now": datetime.now(UTC), "problem_id": problem_id},
    )


def render_problems() -> None:
    st.title("Problemas")
    st.caption(
        "Incidentes da mesma assinatura (tipo + ativo + causa) que se repetem. Candidato com 3 ou mais em "
        "30 dias; uma pessoa promove. Registrada a correção, 30 dias sem reincidência a comprovam."
    )
    try:
        candidatos = query(f"SELECT * FROM {table('ops', 'problem_candidates')} ORDER BY incident_count DESC")
        registros = {
            item["problem_id"]: item for item in query(f"SELECT * FROM {table('ops', 'problem_records')}")
        }
    except Exception:
        st.info("Os problemas são calculados pelo ciclo; aguardando o primeiro após a publicação.")
        return
    if not candidatos:
        st.info("Nenhuma recorrência acima do limite.")
        return
    pode = can(directory(), usuario, MANAGE_PROBLEM)
    for item in candidatos:
        registro = registros.get(item["problem_id"])
        titulo = f"{ESTADO_PROBLEMA.get(item['status'], item['status'])} · {item['subject']} · {item['cause']}"
        with st.expander(titulo, expanded=item["status"] in ("candidato", "ineficaz")):
            st.caption(
                f"{item['incident_count']} incidente(s) · impacto acumulado {item['impact_score_sum']:.2f} · "
                f"{item['open_hours']:.1f} h em aberto · {item['efficacy_detail']}"
            )
            st.write(", ".join(item["incident_ids"] or []))
            if registro:
                st.markdown(
                    f"**Owner:** {registro['owner']} · **prazo:** {registro['due_at']:%d/%m/%Y} · "
                    f"**métrica de sucesso:** {registro['success_metric']}"
                )
                if registro.get("known_error"):
                    st.markdown(f"**Known error:** {registro['known_error']}")
                if registro.get("workaround"):
                    st.markdown(f"**Workaround:** {registro['workaround']}")
                if registro.get("fix_at"):
                    st.markdown(f"**Correção** ({registro['fix_at']:%d/%m/%Y}): {registro['fix_description']}")
                elif pode:
                    descricao = st.text_input("Correção permanente aplicada", key=f"fix-{item['problem_id']}")
                    if st.button("Registrar correção", key=f"fixbtn-{item['problem_id']}", disabled=not descricao):
                        gravar = functools.partial(register_fix, item["problem_id"], descricao)
                        if guarded(MANAGE_PROBLEM, item["problem_id"], gravar):
                            st.rerun()
                continue
            if not pode:
                continue
            owner = st.text_input("Owner", key=f"owner-{item['problem_id']}")
            prazo = st.date_input("Prazo", key=f"due-{item['problem_id']}")
            metrica = st.text_input("Métrica de sucesso", key=f"metric-{item['problem_id']}",
                                    value="nenhuma reincidência em 30 dias")
            known_error = st.text_input("Known error (opcional)", key=f"ke-{item['problem_id']}")
            workaround = st.text_input("Workaround (opcional)", key=f"wa-{item['problem_id']}")
            if st.button("Promover a problema", key=f"promote-{item['problem_id']}", disabled=not owner):
                gravar = functools.partial(promote_problem, item, owner, prazo, metrica, known_error, workaround)
                if guarded(MANAGE_PROBLEM, item["problem_id"], gravar):
                    st.rerun()


SAUDE_ICONE = {"saudavel": "🟢", "degradado": "🟡", "falhando": "🔴", "sem_dados": "⚪"}


def render_connector_health() -> None:
    """Falha silenciosa só deixa de ser silenciosa se alguém a vê."""
    try:
        linhas = query(f"SELECT * FROM {table('ops', 'connector_health')} ORDER BY connector")
    except Exception:
        st.sidebar.caption("Saúde dos conectores: aguardando o primeiro ciclo.")
        return
    st.sidebar.markdown("**Saúde dos conectores**")
    for linha in linhas:
        icone = SAUDE_ICONE.get(linha["status"], "⚪")
        st.sidebar.caption(f"{icone} {linha['connector']} — {linha['status']}: {linha['detail']}")
    if any(linha["status"] in ("degradado", "falhando") for linha in linhas):
        st.sidebar.caption("Procedimento: RB-006 — Connector lag (visão Runbooks).")


def load_recommendations(incident_id: str) -> list[dict]:
    try:
        return query(
            f"SELECT r.*, d.decision, d.reviewer FROM {table('ops', 'recommendations')} r "
            f"LEFT JOIN (SELECT recommendation_id, max_by(decision, at) AS decision, max_by(reviewer, at) AS reviewer "
            f"FROM {table('ops', 'recommendation_reviews')} GROUP BY recommendation_id) d "
            "ON d.recommendation_id = r.recommendation_id "
            "WHERE r.incident_id = :incident_id ORDER BY r.created_at DESC, r.kind",
            {"incident_id": incident_id},
        )
    except Exception:
        return []


def save_recommendation_review(recommendation: dict, decision: str, reviewer: str) -> None:
    execute(
        f"INSERT INTO {table('ops', 'recommendation_reviews')} "
        "(review_id, recommendation_id, incident_id, decision, reviewer, at, note) "
        "VALUES (:review_id, :recommendation_id, :incident_id, :decision, :reviewer, :at, NULL)",
        {
            "review_id": str(uuid.uuid4()),
            "recommendation_id": recommendation["recommendation_id"],
            "incident_id": recommendation["incident_id"],
            "decision": decision,
            "reviewer": reviewer,
            "at": datetime.now(UTC),
        },
    )


ROTULO_RECOMENDACAO = {"verificar": "Verificar", "agir": "Agir", "coletar_evidencia": "Coletar evidência"}


def _safe_query(statement: str, parameters: dict | None = None) -> list[dict]:
    """Read model que ainda não existe (antes do primeiro ciclo) aparece vazio, sem quebrar a tela."""
    try:
        return query(statement, parameters)
    except Exception:
        return []


def load_incident_runbooks(incident_id: str) -> list[dict]:
    return _safe_query(
        f"SELECT ir.reason, ir.level, r.* FROM {table('ops', 'incident_runbooks')} ir "
        f"JOIN {table('ops', 'runbooks')} r ON r.runbook_id = ir.runbook_id "
        "WHERE ir.incident_id = :incident_id ORDER BY ir.level, r.status, r.runbook_id",
        {"incident_id": incident_id},
    )


def follow_runbook(incident_id: str, runbook_id: str) -> None:
    execute(
        f"INSERT INTO {table('ops', 'runbook_usage')} (usage_id, incident_id, runbook_id, actor, at) "
        "VALUES (:usage_id, :incident_id, :runbook_id, :actor, :at)",
        {
            "usage_id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "runbook_id": runbook_id,
            "actor": usuario,
            "at": datetime.now(UTC),
        },
    )


def render_runbooks_and_similar(incident: dict) -> None:
    """O procedimento que se aplica e o que já aconteceu antes — com o motivo de cada escolha."""
    st.subheader("Runbook e casos anteriores")
    runbooks = load_incident_runbooks(incident["incident_id"])
    if not runbooks:
        st.caption("Sem runbook para este tipo de incidente.")
    usados = {
        row["runbook_id"]
        for row in _safe_query(
            f"SELECT runbook_id FROM {table('ops', 'runbook_usage')} WHERE incident_id = :incident_id",
            {"incident_id": incident["incident_id"]},
        )
    }
    pode = can(directory(), usuario, FOLLOW_RUNBOOK)
    for runbook in runbooks:
        rotulo = f"{runbook['runbook_id']} — {runbook['title']} · motivo: {runbook['reason']}"
        if runbook["status"] == "rascunho":
            rotulo += " · ⚠️ rascunho, ainda não revisado"
        with st.expander(rotulo, expanded=runbook["level"] == 1):
            for numero, passo in enumerate(runbook["steps"] or [], start=1):
                st.markdown(f"{numero}. {passo}")
            st.caption(f"dono: {runbook['owner']} · {runbook['source_file']}")
            if runbook["runbook_id"] in usados:
                st.caption("Uso registrado neste incidente.")
            elif pode and st.button(f"Segui o {runbook['runbook_id']}", key=f"follow-{runbook['runbook_id']}"):
                gravar = functools.partial(follow_runbook, incident["incident_id"], runbook["runbook_id"])
                if guarded(FOLLOW_RUNBOOK, f"{incident['incident_id']}:{runbook['runbook_id']}", gravar):
                    st.rerun()

    similares = _safe_query(
        f"SELECT * FROM {table('ops', 'similar_incidents')} WHERE incident_id = :incident_id ORDER BY rank",
        {"incident_id": incident["incident_id"]},
    )
    if not similares:
        st.caption("Nenhum caso semelhante nos últimos 90 dias.")
        return
    st.markdown("**Casos semelhantes**")
    for caso in similares:
        if caso["hours_to_recover"] is not None:
            resolucao = f"recuperado em {caso['hours_to_recover']:.1f} h"
        else:
            resolucao = f"estado: {caso['similar_state']}"
        st.markdown(f"- `{caso['similar_id']}` · {caso['reason']} · {resolucao}")
        if caso.get("fix_description"):
            workaround = f" · workaround: {caso['workaround']}" if caso.get("workaround") else ""
            st.caption(f"   correção comprovada: {caso['fix_description']}{workaround}")


def _efficacy_text(medida: dict | None) -> str:
    if medida is None:
        return "sem uso registrado"
    if medida["efficacy"] is None:
        return f"{medida['pending']} uso(s) aguardando desfecho"
    decididos = medida["successes"] + medida["failures"]
    pequena = ", amostra pequena" if medida["small_sample"] else ""
    return (
        f"eficácia {medida['efficacy'] * 100:.0f}% ({medida['successes']} de {decididos}{pequena})"
        f" · {medida['pending']} pendente(s)"
    )


def render_runbooks_view() -> None:
    st.title("Runbooks")
    st.caption("Catálogo versionado (muda por PR), eficácia medida e o que os problemas resolvidos ensinaram.")
    catalogo = _safe_query(f"SELECT * FROM {table('ops', 'runbooks')} ORDER BY runbook_id")
    if not catalogo:
        st.info("O catálogo é carregado pelo ciclo; aguardando o primeiro após a publicação.")
        return
    eficacia = {row["runbook_id"]: row for row in _safe_query(f"SELECT * FROM {table('ops', 'runbook_efficacy')}")}
    for runbook in catalogo:
        tipos = ", ".join(runbook["incident_types"] or [])
        disparo = tipos or ("conectores" if runbook["connector"] else "sem disparo hoje")
        aviso = " · ⚠️ rascunho" if runbook["status"] == "rascunho" else ""
        st.markdown(f"**{runbook['runbook_id']} — {runbook['title']}**{aviso}")
        st.caption(f"{disparo} · {_efficacy_text(eficacia.get(runbook['runbook_id']))}")

    conhecimento = _safe_query(f"SELECT * FROM {table('ops', 'knowledge_items')} ORDER BY runbook_id")
    st.subheader("Conhecimento de problemas resolvidos")
    if not conhecimento:
        st.caption("Nenhum problema resolvido com correção comprovada ainda.")
    for item in conhecimento:
        with st.expander(f"{item['symptom']} · causa {item['cause']} · {item['runbook_id'] or 'sem runbook'}"):
            st.markdown(f"**Correção comprovada:** {item['fix_description']}")
            if item.get("known_error"):
                st.markdown(f"**Known error:** {item['known_error']}")
            if item.get("workaround"):
                st.markdown(f"**Workaround:** {item['workaround']}")
            st.markdown("**Sugestão para o PR do runbook** (nada é gravado automaticamente):")
            st.code(item["suggestion"], language=None)


CATEGORIA_CUSTO = {"dominio": "Com dono", "plataforma": "Pool da plataforma EICT", "nao_alocado": "Não alocado"}


def render_costs() -> None:
    """Showback (PRD-070 F2/F3/F5): de quem é o custo, o que não tem dono e quanto custa cada unidade."""
    st.title("Custos")
    st.caption("Showback, não chargeback. Mapeamento em `allocation/*.yaml`, alterado só por PR.")
    conciliacoes = _safe_query(f"SELECT * FROM {table('ops', 'cost_reconciliation')} ORDER BY period_label DESC")
    if not conciliacoes:
        st.info("O showback é calculado pelo ciclo, no máximo uma vez por hora; aguardando o primeiro.")
        return
    periodo = st.radio("Período", [row["period_label"] for row in conciliacoes], horizontal=True)
    conciliacao = next(row for row in conciliacoes if row["period_label"] == periodo)
    moeda, base = conciliacao["currency"], conciliacao["price_basis"]
    estado = conciliacao["period_status"]
    if conciliacao["watermark"]:
        estado += f" · dados do billing até {conciliacao['watermark']:%d/%m %H:%M} UTC"
    st.caption(f"{estado} · escopo: {conciliacao['scope']} · calculado em {conciliacao['computed_at']:%d/%m %H:%M} UTC")
    if conciliacao["reconciled"]:
        diferenca = fmt_money(conciliacao["difference"], moeda, periodo, base)
        st.success(f"Reconciliado com o billing: diferença {diferenca}")
    else:
        st.error(f"Não reconciliado — {conciliacao['reason']}. Os valores abaixo não fecham com o billing.")
    colunas = st.columns(4)
    colunas[0].metric("Total do billing", fmt_money(conciliacao["total_billing"], moeda, periodo, base))
    colunas[1].metric("Com dono", fmt_money(conciliacao["allocated"], moeda, periodo, base))
    colunas[2].metric("Pool da plataforma", fmt_money(conciliacao["platform_pool"], moeda, periodo, base))
    colunas[3].metric("Não alocado", fmt_money(conciliacao["unallocated"], moeda, periodo, base))
    st.caption(
        f"Qualidade do mapeamento: {fmt_share(conciliacao['allocated_share'])} do custo com dono (pool fora da conta)"
        + (f" · {conciliacao['unpriced_dbus']:.2f} DBUs sem preço de lista" if conciliacao["unpriced_dbus"] else "")
    )

    alocacao = _safe_query(
        f"SELECT * FROM {table('ops', 'cost_allocation')} WHERE period_label = :periodo ORDER BY category, cost DESC",
        {"periodo": periodo},
    )
    for categoria, titulo in CATEGORIA_CUSTO.items():
        linhas = [row for row in alocacao if row["category"] == categoria]
        if not linhas:
            continue
        st.subheader(titulo)
        st.dataframe(
            [
                {
                    "Unidade de negócio": row["business_unit"],
                    "Domínio": row["domain"],
                    "Produto": row["product"],
                    "Dono": row["owner"],
                    "Recurso": f"{row['resource_kind']} {row['resource_name'] or row['resource_id']}".strip(),
                    "Motivo": row["reason"],
                    "Custo": fmt_money(row["cost"], moeda, periodo, base),
                }
                for row in linhas
            ],
            use_container_width=True,
            hide_index=True,
        )

    unidades = _safe_query(
        f"SELECT * FROM {table('ops', 'cost_units')} WHERE period_label = :periodo ORDER BY unit, subject",
        {"periodo": periodo},
    )
    st.subheader("Custo por unidade")
    st.dataframe(
        [
            {
                "Unidade": row["unit"],
                "Sujeito": row["subject"],
                "Dono": row["owner"],
                "Mediana": fmt_money(row["median"], moeda, periodo, base),
                "Média": fmt_money(row["mean"], moeda, periodo, base),
                "n": row["n"],
                "Estado": row["status"],
                "Fórmula": row["formula"],
            }
            for row in unidades
        ],
        use_container_width=True,
        hide_index=True,
    )

    regras = _safe_query(f"SELECT * FROM {table('ops', 'allocation_rules')} WHERE status <> 'ativa'")
    if regras:
        st.subheader("Regras com problema")
        for regra in regras:
            st.warning(f"{regra['source_file']} · {regra['status']} · {regra['job_name']} {regra['detail']}".strip())


FONTE_ECONOMIA = {
    "regressao_custo": "Regressão de custo",
    "execucao_falhada": "Execução falhada",
    "schedule_fora_prod": "Schedule fora de prod",
    "warehouse_ocioso": "Warehouse ocioso",
}
ESTADO_ECONOMIA = {
    "em_medicao": "🟡 em medição",
    "realizada": "🟢 realizada",
    "nao_realizada": "🔴 não realizada",
    "amostra_insuficiente": "⏳ amostra insuficiente",
    "expirada": "⛔ expirada",
    "realizada_com_efeito_colateral": "🟠 realizada com efeito colateral (fora do KPI)",
}


def _run_savings_action(statements) -> None:
    for statement, parameters in statements:
        execute(statement, parameters)


def _savings_action(action: str, target: str, build) -> None:
    """Valida a transição antes de autorizar: transição inválida não chega à trilha nem à tabela."""
    try:
        statements = build()
    except SavingsActionError as exc:
        st.error(str(exc))
        return
    if guarded(action, target, functools.partial(_run_savings_action, statements)):
        st.rerun()


def _estimativa(item: dict) -> str:
    texto = fmt_money(item["estimate_usd"], item["currency"], item["period_label"], item["price_basis"])
    if item["estimate_low"] != item["estimate_high"]:
        texto += f" (faixa {float(item['estimate_low']):,.4f}–{float(item['estimate_high']):,.4f}, n={item['n']})"
    return texto + (" · histórico curto" if item["short_history"] else "")


def _detector_text(item: dict) -> str:
    nome = FONTE_ECONOMIA.get(item["source"], item["source"])
    if item["status"] == "nao_avaliado":
        return f"{nome}: não avaliado — {item['reason']}"
    return f"{nome}: {item['opportunity_count']} oportunidade(s), {item['below_threshold']} abaixo do limiar"


def render_opportunity(item: dict) -> None:
    marca = "" if item["counted"] else " · contida em outra do mesmo job (não soma)"
    if item["status"] == "em_iniciativa":
        marca = " · em andamento numa iniciativa (não soma)"
    fonte = FONTE_ECONOMIA.get(item["source"], item["source"])
    with st.expander(f"{fonte} · {item['subject_name']} · {_estimativa(item)}{marca}"):
        confianca = f"{item['confidence']:.2f}" if item["confidence"] is not None else item["confidence_label"]
        st.markdown(f"**Recomendação:** {item['recommendation']}")
        st.caption(
            f"Fórmula: {item['formula']} · confiança {confianca} · risco **{item['risk']}**: {item['risk_reason']}"
        )
        st.caption(
            f"Dono: {item['owner'] or '—'}"
            + (f" · {item['note']}" if item["note"] else "")
            + (f" · hipótese {item['hypothesis_code']}" if item["hypothesis_code"] else "")
            + f" · evidências: {', '.join(item['evidence'] or [])}"
        )
        if item["status"] != "identificada":
            return
        chave = item["opportunity_id"]
        if can(directory(), usuario, APPROVE_SAVING) and st.button("Aprovar", key=f"apv-{chave}"):
            _savings_action(
                APPROVE_SAVING, chave, lambda: approve_statements(item, usuario, datetime.now(UTC), table)
            )
        if can(directory(), usuario, DISCARD_SAVING):
            motivo = st.text_input("Motivo do descarte", key=f"mot-{chave}")
            if st.button("Descartar", key=f"dsc-{chave}"):
                _savings_action(
                    DISCARD_SAVING, chave,
                    lambda: discard_statements(item, usuario, motivo, datetime.now(UTC), table),
                )


def render_initiative(item: dict) -> None:
    estado = ESTADO_ECONOMIA.get(item["measured_state"], item["state"])
    auto = " · ⚠️ autoaprovada" if item["self_approved"] else ""
    fonte = FONTE_ECONOMIA.get(item["source"], item["source"])
    with st.expander(f"{fonte} · {item['subject']} · {estado}{auto}"):
        st.caption(
            f"Aprovada por {item['approved_by']} em {item['approved_at']:%d/%m %H:%M} UTC · estimativa congelada "
            f"US$ {float(item['estimate_usd']):,.4f}/mês · {item['formula']}"
        )
        if item["state"] == "implementada":
            st.caption(
                f"Implementada por {item['implemented_by']} em {item['implemented_at']:%d/%m %H:%M} UTC · "
                f"{item['change_ref']}"
            )
            if item["measured_state"] in ("realizada", "nao_realizada", "realizada_com_efeito_colateral"):
                valor = item["net_usd"] if item["net_usd"] is not None else item["gross_usd"]
                st.metric(
                    "Economia medida (mensal)", f"US$ {float(valor):,.4f}",
                    help=f"{item['measured_unit']}: {item['baseline_median']} → {item['after_median']} "
                    f"(n={item['n_before']} antes, {item['n_after']} depois)",
                )
            if item.get("measured_reason"):
                st.caption(item["measured_reason"])
            return
        if not can(directory(), usuario, IMPLEMENT_SAVING):
            return
        chave = item["initiative_id"]
        referencia = st.text_input("Commit ou link do PR", key=f"ref-{chave}")
        custo = st.number_input("Custo da implementação (US$, opcional)", min_value=0.0, value=0.0, key=f"cst-{chave}")
        if st.button("Registrar implementação", key=f"imp-{chave}"):
            _savings_action(
                IMPLEMENT_SAVING, chave,
                lambda: implement_statements(item, usuario, referencia, custo or None, datetime.now(UTC), table),
            )


def render_savings() -> None:
    """PRD-070 F6/F7: o ciclo propõe e mede; a pessoa aprova, descarta ou registra a implementação."""
    st.title("Economia")
    st.caption("Economia potencial não é economia realizada. Nada é alterado pela plataforma.")
    detectores = _safe_query(f"SELECT * FROM {table('ops', 'savings_detectors')} ORDER BY source")
    if not detectores:
        st.info("As oportunidades são calculadas pelo ciclo, no máximo uma vez por hora; aguardando o primeiro.")
        return
    if detectores[0].get("config_error"):
        st.warning(f"Política recusada, usando os padrões: {detectores[0]['config_error']}")
    st.caption(
        " · ".join(_detector_text(item) for item in detectores)
        + f" · calculado em {detectores[0]['computed_at']:%d/%m %H:%M} UTC"
    )
    oportunidades = _safe_query(
        f"SELECT * FROM {table('ops', 'savings_opportunities')} ORDER BY counted DESC, estimate_usd DESC"
    )
    st.subheader("Oportunidades")
    if not oportunidades:
        st.caption("Nenhuma oportunidade acima do limiar.")
    for item in oportunidades:
        render_opportunity(item)
    iniciativas = _safe_query(
        "SELECT i.*, r.state AS measured_state, r.gross_usd, r.net_usd, r.unit AS measured_unit, "
        "r.baseline_median, r.after_median, r.n_before, r.n_after, r.reason AS measured_reason "
        f"FROM {table('ops', 'savings_initiatives')} i "
        f"LEFT JOIN {table('ops', 'savings_realization')} r ON i.initiative_id = r.initiative_id "
        "WHERE i.state <> 'descartada' ORDER BY i.approved_at DESC"
    )
    st.subheader("Iniciativas")
    if not iniciativas:
        st.caption("Nenhuma iniciativa aprovada ainda.")
    for item in iniciativas:
        render_initiative(item)


def render_recommendations(incident: dict) -> None:
    """Read-only: a plataforma recomenda, uma pessoa decide e executa."""
    recomendacoes = load_recommendations(incident["incident_id"])
    st.subheader("Recomendações")
    if not recomendacoes:
        st.caption("Nenhuma recomendação para este incidente.")
        return
    st.caption("Nada aqui é executado pela plataforma. Aceitar registra a decisão; a ação é sua.")
    aplicaveis = load_incident_runbooks(incident["incident_id"])
    if aplicaveis:
        st.caption(f"Runbook aplicável: {aplicaveis[0]['runbook_id']} — {aplicaveis[0]['title']}")
    pode = can(directory(), usuario, REVIEW_RECOMMENDATION)
    for rec in recomendacoes:
        rotulo = ROTULO_RECOMENDACAO.get(rec["kind"], rec["kind"])
        st.markdown(f"**{rotulo}** — {rec['text']}")
        evidencias = ", ".join(rec.get("evidence_ids") or []) or "—"
        st.caption(f"base: {rec['basis']} · evidências: {evidencias} · responsável: {rec['owner_role']}")
        if rec.get("decision"):
            st.caption(f"{rec['decision']} por {rec['reviewer']}")
            continue
        if not pode:
            continue
        colunas = st.columns(2)
        for coluna, texto, decisao in ((colunas[0], "Aceitar", "accepted"), (colunas[1], "Rejeitar", "rejected")):
            if coluna.button(texto, key=f"rec-{decisao}-{rec['recommendation_id']}"):
                gravar = functools.partial(save_recommendation_review, rec, decisao, usuario)
                if guarded(REVIEW_RECOMMENDATION, rec["recommendation_id"], gravar):
                    st.rerun()


def acknowledge(incident: dict, email: str) -> None:
    for statement, parameters in acknowledge_statements(incident, email, datetime.now(UTC), table):
        execute(statement, parameters)
    load_incidents.clear()


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
render_connector_health()
visoes = ["Resumo executivo", "Incidentes", "Problemas", "Runbooks", "Custos", "Economia"] + (
    ["Auditoria"] if can(directory(), usuario, VIEW_AUDIT) else []
)
visao = st.sidebar.radio("Visão", visoes)
if visao == "Problemas":
    render_problems()
    st.stop()
if visao == "Runbooks":
    render_runbooks_view()
    st.stop()
if visao == "Custos":
    render_costs()
    st.stop()
if visao == "Economia":
    render_savings()
    st.stop()
if visao == "Resumo executivo":
    render_executive()
    st.stop()
if visao == "Auditoria":
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
if incident.get("acknowledged_at"):
    st.caption(f"Reconhecido por {incident['acknowledged_by']} em {incident['acknowledged_at']:%d/%m %H:%M} UTC")
elif can_acknowledge(incident) and can(directory(), usuario, ACKNOWLEDGE_INCIDENT):
    if st.button("Reconhecer incidente", key=f"ack-{incident['incident_id']}"):
        if guarded(ACKNOWLEDGE_INCIDENT, incident["incident_id"], functools.partial(acknowledge, incident, usuario)):
            st.rerun()

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

render_runbooks_and_similar(incident)
render_recommendations(incident)

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
