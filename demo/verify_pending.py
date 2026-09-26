"""Janela de verificação das features que esperam execução real, dentro da cota da Free Edition.

Uma sequência curta (4 runs, ≈ 34 min previstos) verifica as onze features pendentes. Antes de
gastar qualquer coisa, confere se a conta ainda está bloqueada. Antes de cada passo, confere o
orçamento. Recusa de cota no meio para a janela sem perder o que já foi verificado — a próxima
execução retoma do primeiro passo pendente. No fim, sempre, desliga o App e o warehouse.

O job grande (`sales_daily`) nunca é disparado daqui: só os recursos da allowlist.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PLATFORM = ROOT / "eict-platform"
WORKLOAD = ROOT / "eict-demo-workload"
STATE_FILE = HERE / ".verify_state.json"
REPORT_FILE = HERE / "verification_report.md"

APP_NAME = "eict-console-dev"
ALLOWED_RUNS = frozenset({"sales_daily_small", "eict_cycle", "eict_console"})
REFUSAL_MARKERS = ("disabled temporarily", "due to workspace or account status")
MAX_WINDOW_AGE = timedelta(hours=24)
PARTIAL_STAGES = "bootstrap,collect,medallion,correlate"

VERIFICADO = "verificado"
FALHOU = "falhou"
NAO_ALCANCADO = "nao_alcancado"

FEATURES = {
    "F1": "Risco de SLA",
    "F2": "Auditoria/RBAC",
    "F3": "Saúde dos conectores",
    "F4": "Baseline de custo",
    "F5": "Resumo executivo",
    "F6": "Reconhecimento de incidente",
    "F7": "Recomendações",
    "F8": "Gestão de problemas",
    "F9": "Runbooks",
    "F10": "FinOps A (alocação)",
    "F11": "FinOps B (economia)",
}
EXECUTIVE_METRICS = 14
RUNBOOK_COUNT = 9


class QuotaRefused(RuntimeError):
    """A conta recusou compute: parar agora, sem perder o que já foi verificado."""


class CommandFailed(RuntimeError):
    """Um comando do CLI falhou por outro motivo."""


Runner = Callable[[list[str], Path | None], tuple[int, str]]


def subprocess_runner(command: list[str], cwd: Path | None) -> tuple[int, str]:
    resultado = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return resultado.returncode, (resultado.stdout or "") + (resultado.stderr or "")


def is_refusal(output: str) -> bool:
    texto = output.lower()
    return any(marca in texto for marca in REFUSAL_MARKERS)


class Cli:
    def __init__(self, profile: str, runner: Runner = subprocess_runner) -> None:
        self.profile = profile
        self.runner = runner

    def run(self, args: list[str], cwd: Path | None = None) -> str:
        codigo, saida = self.runner(["databricks", *args, "--profile", self.profile], cwd)
        if is_refusal(saida):
            raise QuotaRefused(saida.strip()[-300:])
        if codigo != 0:
            raise CommandFailed(f"databricks {' '.join(args[:3])}: {saida.strip()[-300:]}")
        return saida

    def bundle_run(self, resource: str, bundle_dir: Path, variables: str, params: str = "") -> str:
        if resource not in ALLOWED_RUNS:
            raise ValueError(f"recurso {resource} fora da allowlist da janela: {sorted(ALLOWED_RUNS)}")
        args = ["bundle", "run", resource, "-t", "dev", f"--var={variables}"]
        if params:
            args += ["--params", params]
        return self.run(args, bundle_dir)

    def query(self, sql: str) -> list[dict]:
        saida = self.run(["experimental", "aitools", "tools", "query", sql, "-o", "json"])
        inicio = saida.find("[")
        try:
            return json.loads(saida[inicio:]) if inicio >= 0 else []
        except ValueError as exc:
            raise CommandFailed(f"resposta da consulta ilegível: {exc}") from exc


@dataclass
class State:
    window_started_at: str
    done: list[str] = field(default_factory=list)
    minutes: float = 0.0
    runs: int = 0
    sla_incident_id: str = ""
    features: dict[str, dict] = field(default_factory=dict)
    steps: dict[str, dict] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def started(self) -> datetime:
        return datetime.fromisoformat(self.window_started_at)


def load_state(path: Path, now: datetime, reset: bool) -> State:
    if reset or not path.exists():
        return State(now.isoformat())
    estado = State(**json.loads(path.read_text(encoding="utf-8")))
    if now - estado.started > MAX_WINDOW_AGE:
        raise SystemExit(
            f"janela iniciada em {estado.window_started_at} tem mais de 24 h: a sequência do SLA perdeu "
            "sentido. Rode com --reset para começar outra."
        )
    return estado


def save_state(path: Path, state: State) -> None:
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class Budget:
    max_minutes: float = 45.0
    max_runs: int = 8

    def fits(self, state: State, step: Step) -> bool:
        return state.minutes + step.predicted_min <= self.max_minutes and state.runs + step.runs <= self.max_runs


@dataclass(frozen=True)
class Config:
    warehouse_id: str
    catalog: str = "workspace"
    schema_prefix: str = "eict_"
    workload_repo: str = ""
    sla_wait_min: float = 8.0
    manual: bool = True
    precheck: bool = True

    def table(self, layer: str, name: str) -> str:
        return f"{self.catalog}.{self.schema_prefix}{layer}.{name}"

    @property
    def platform_vars(self) -> str:
        variaveis = f"warehouse_id={self.warehouse_id}"
        return variaveis + (f",workload_repo={self.workload_repo}" if self.workload_repo else "")


@dataclass(frozen=True)
class Step:
    step_id: str
    runs: int
    predicted_min: float
    action: Callable[[Window], None]
    always: bool = False


def _sql_time(value: datetime) -> str:
    return f"TIMESTAMP '{value.astimezone(UTC):%Y-%m-%d %H:%M:%S}'"


def parse_time(value: object) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    texto = str(value).strip().replace(" ", "T")
    try:
        instante = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    return instante if instante.tzinfo else instante.replace(tzinfo=UTC)


def _audit_verify(rows: list[dict]):
    sys.path.insert(0, str(PLATFORM / "app"))
    from audit import verify

    return verify([{**row, "at": parse_time(row.get("at"))} for row in rows])


class Window:
    def __init__(
        self,
        cli: Cli,
        config: Config,
        state: State,
        budget: Budget,
        wait: Callable[[float], None] = time.sleep,
        ask: Callable[[str], str] = input,
        clock: Callable[[], float] = time.monotonic,
        audit_verify: Callable[[list[dict]], object] = _audit_verify,
    ) -> None:
        self.cli = cli
        self.config = config
        self.state = state
        self.budget = budget
        self.wait = wait
        self.ask = ask
        self.clock = clock
        self.audit_verify = audit_verify

    def record(self, feature: str, status: str, detail: str = "") -> None:
        self.state.features[feature] = {"status": status, "detail": detail}

    def scalar(self, sql: str) -> object:
        linhas = self.cli.query(sql)
        return next(iter(linhas[0].values())) if linhas else None

    @property
    def since(self) -> str:
        return _sql_time(self.state.started)


def precheck(w: Window) -> None:
    """Sem custo. O status do App pode ter ficado do último bloqueio mesmo depois de a cota voltar:
    por isso a mensagem de aborto oferece `--skip-precheck` — e o primeiro disparo recusado também
    não gasta compute."""
    if not w.config.precheck:
        return
    try:
        w.cli.run(["apps", "get", APP_NAME, "-o", "json"])
        w.cli.run(["warehouses", "get", w.config.warehouse_id, "-o", "json"])
    except QuotaRefused as exc:
        raise QuotaRefused(
            f"{exc} — o status pode ser do último bloqueio; se a cota já voltou, rode com --skip-precheck "
            "(se ainda estiver bloqueada, o primeiro disparo é recusado sem gastar compute)"
        ) from exc


def deploy(w: Window) -> None:
    w.cli.run(["bundle", "deploy", "-t", "dev", f"--var={w.config.platform_vars}"], PLATFORM)
    w.cli.run(["bundle", "deploy", "-t", "dev", f"--var=warehouse_id={w.config.warehouse_id}"], WORKLOAD)


def light_run(w: Window) -> None:
    w.cli.bundle_run("sales_daily_small", WORKLOAD, f"warehouse_id={w.config.warehouse_id}", "heavy=false")


def wait_sla(w: Window) -> None:
    print(f"esperando {w.config.sla_wait_min:.0f} min para o prazo de frescor apertar (sem compute)")
    w.wait(w.config.sla_wait_min * 60)


def cycle_partial(w: Window) -> None:
    w.cli.bundle_run("eict_cycle", PLATFORM, w.config.platform_vars, f"stages={PARTIAL_STAGES}")
    incidente = w.scalar(
        f"SELECT incident_id FROM {w.config.table('ops', 'incidents')} "
        f"WHERE type = 'sla_risk' AND detected_at >= {w.since} ORDER BY detected_at DESC LIMIT 1"
    )
    w.state.sla_incident_id = str(incidente or "")
    if not incidente:
        w.record("F1", FALHOU, "nenhum sla_risk aberto no ciclo parcial (espera curta? ver SLA_WAIT_MIN)")


def app_deploy(w: Window) -> None:
    w.cli.bundle_run("eict_console", PLATFORM, w.config.platform_vars)


def manual_ack(w: Window) -> None:
    if not w.config.manual:
        for feature in ("F2", "F6"):
            w.record(feature, NAO_ALCANCADO, "passo manual pulado (--no-manual)")
        return
    alvo = w.state.sla_incident_id or "um incidente ativo qualquer"
    w.ask(
        f"\nPASSO MANUAL: abra o console ({APP_NAME}), visão Incidentes, e clique em "
        f"'Reconhecer incidente' em {alvo}. Isso também grava a trilha de auditoria.\n"
        "Pressione Enter quando terminar (a verificação é feita por SQL em seguida)... "
    )


def cycle_full(w: Window) -> None:
    w.cli.bundle_run("eict_cycle", PLATFORM, w.config.platform_vars)


MANUAL_FEATURES = frozenset({"F2", "F6"})


def _check(w: Window, feature: str, fn: Callable[[Window], tuple[str, str]]) -> None:
    if feature in MANUAL_FEATURES and not w.config.manual:
        return
    try:
        status, detalhe = fn(w)
    except CommandFailed as exc:
        status, detalhe = FALHOU, f"consulta falhou: {exc}"
    w.record(feature, status, detalhe)


def check_sla(w: Window) -> tuple[str, str]:
    if not w.state.sla_incident_id:
        return FALHOU, "nenhum sla_risk aberto nesta janela"
    estado = w.scalar(
        f"SELECT state FROM {w.config.table('ops', 'incidents')} WHERE incident_id = '{w.state.sla_incident_id}'"
    )
    desfechos = w.scalar(
        f"SELECT count(*) AS n FROM {w.config.table('ops', 'sla_predictions')} "
        f"WHERE predicted_at >= {w.since} AND outcome IS NOT NULL"
    )
    if estado == "recovered" and int(desfechos or 0) > 0:
        return VERIFICADO, f"{w.state.sla_incident_id} aberto e recuperado; {desfechos} previsão(ões) com desfecho"
    return FALHOU, f"{w.state.sla_incident_id} em '{estado}'; previsões com desfecho: {desfechos}"


def check_audit(w: Window) -> tuple[str, str]:
    linhas = w.cli.query(f"SELECT * FROM {w.config.table('ops', 'audit_log')} ORDER BY seq")
    recentes = [linha for linha in linhas if (parse_time(linha.get("at")) or w.state.started) >= w.state.started]
    if not recentes:
        return FALHOU, "nenhuma linha de auditoria nesta janela (o passo manual foi feito?)"
    veredito = w.audit_verify(linhas)
    if veredito.status != "integra":
        return FALHOU, f"cadeia {veredito.status}: {veredito.detail}"
    return VERIFICADO, f"{len(recentes)} linha(s) nesta janela; cadeia íntegra ({len(linhas)} no total)"


def check_connectors(w: Window) -> tuple[str, str]:
    linhas = w.cli.query(
        f"SELECT connector, status FROM {w.config.table('ops', 'connector_health')} WHERE evaluated_at >= {w.since}"
    )
    validos = {"saudavel", "degradado", "falhando", "sem_dados"}
    if linhas and all(linha["status"] in validos for linha in linhas):
        return VERIFICADO, ", ".join(f"{linha['connector']}: {linha['status']}" for linha in linhas)
    return FALHOU, f"linhas nesta janela: {linhas or 'nenhuma'}"


def check_cost(w: Window) -> tuple[str, str]:
    n = w.scalar(
        f"SELECT n FROM {w.config.table('ops', 'executive_summary')} "
        f"WHERE metric_id = 'incremental_cost_usd' AND computed_at >= {w.since}"
    )
    if n is not None and int(n) > 0:
        return VERIFICADO, f"evidência parcial: custo incremental confirmado pelo billing em {n} incidente(s)"
    return FALHOU, "nenhum custo confirmado pelo billing nesta janela"


def check_executive(w: Window) -> tuple[str, str]:
    n = w.scalar(
        f"SELECT count(DISTINCT metric_id) AS n FROM {w.config.table('ops', 'executive_summary')} "
        f"WHERE computed_at >= {w.since}"
    )
    if int(n or 0) == EXECUTIVE_METRICS:
        return VERIFICADO, f"{n} métricas recalculadas nesta janela"
    return FALHOU, f"{n} de {EXECUTIVE_METRICS} métricas recalculadas"


def check_ack(w: Window) -> tuple[str, str]:
    reconhecidos = w.scalar(
        f"SELECT count(*) AS n FROM {w.config.table('ops', 'incidents')} WHERE acknowledged_at >= {w.since}"
    )
    auditados = w.scalar(
        f"SELECT count(*) AS n FROM {w.config.table('ops', 'audit_log')} "
        f"WHERE action = 'acknowledge_incident' AND decision = 'allowed' AND at >= {w.since}"
    )
    if int(reconhecidos or 0) > 0 and int(auditados or 0) > 0:
        return VERIFICADO, f"{reconhecidos} incidente(s) reconhecido(s), {auditados} linha(s) de auditoria"
    return FALHOU, f"reconhecidos: {reconhecidos}; auditados: {auditados}"


def check_recommendations(w: Window) -> tuple[str, str]:
    n = w.scalar(
        f"SELECT count(*) AS n FROM {w.config.table('ops', 'recommendations')} r "
        f"JOIN {w.config.table('ops', 'incidents')} i ON r.incident_id = i.incident_id "
        f"WHERE i.detected_at >= {w.since}"
    )
    if int(n or 0) > 0:
        return VERIFICADO, f"{n} recomendação(ões) para incidentes desta janela"
    return FALHOU, "nenhuma recomendação para incidentes desta janela"


def check_problems(w: Window) -> tuple[str, str]:
    linhas = w.cli.query(f"DESCRIBE HISTORY {w.config.table('ops', 'problem_candidates')} LIMIT 1")
    ultimo = parse_time(linhas[0].get("timestamp")) if linhas else None
    if ultimo is not None and ultimo >= w.state.started:
        return VERIFICADO, f"candidatos recalculados em {ultimo:%d/%m %H:%M} UTC"
    return FALHOU, f"última escrita: {ultimo}"


def check_runbooks(w: Window) -> tuple[str, str]:
    catalogo = w.scalar(f"SELECT count(*) AS n FROM {w.config.table('ops', 'runbooks')}")
    ligados = 0
    if w.state.sla_incident_id:
        ligados = w.scalar(
            f"SELECT count(*) AS n FROM {w.config.table('ops', 'incident_runbooks')} "
            f"WHERE incident_id = '{w.state.sla_incident_id}'"
        )
    if int(catalogo or 0) == RUNBOOK_COUNT and int(ligados or 0) > 0:
        return VERIFICADO, f"{catalogo} runbooks; {ligados} ligado(s) ao sla_risk"
    return FALHOU, f"runbooks: {catalogo}; ligados ao sla_risk: {ligados}"


def check_finops_a(w: Window) -> tuple[str, str]:
    periodos = w.cli.query(
        f"SELECT period_label, reconciled, total_billing FROM {w.config.table('ops', 'cost_reconciliation')} "
        f"WHERE computed_at >= {w.since}"
    )
    sem_id = w.scalar(
        f"SELECT sum(cost) AS c FROM {w.config.table('ops', 'cost_allocation')} "
        f"WHERE reason LIKE 'recurso não identificado%' AND computed_at >= {w.since}"
    )
    total = sum(float(linha.get("total_billing") or 0) for linha in periodos)
    fracao = f"{float(sem_id or 0) / total:.1%}" if total else "sem total"
    detalhe = (
        "; ".join(f"{linha['period_label']} reconciliado={linha['reconciled']}" for linha in periodos)
        + f"; recurso não identificado: {fracao} do total (valida A2/A3 da FinOps A)"
    )
    return (VERIFICADO if len(periodos) == 2 else FALHOU), detalhe


def check_finops_b(w: Window) -> tuple[str, str]:
    linhas = w.cli.query(
        f"SELECT source, status, reason FROM {w.config.table('ops', 'savings_detectors')} "
        f"WHERE computed_at >= {w.since}"
    )
    ocioso = next((linha for linha in linhas if linha["source"] == "warehouse_ocioso"), None)
    detalhe = f"{len(linhas)} fonte(s); warehouse_ocioso: " + (
        f"{ocioso['status']} {ocioso.get('reason') or ''}".strip() if ocioso else "ausente"
    )
    return (VERIFICADO if len(linhas) == 4 else FALHOU), detalhe + " (valida query.history da FinOps B)"


CHECKS: tuple[tuple[str, Callable[[Window], tuple[str, str]]], ...] = (
    ("F1", check_sla),
    ("F2", check_audit),
    ("F3", check_connectors),
    ("F4", check_cost),
    ("F5", check_executive),
    ("F6", check_ack),
    ("F7", check_recommendations),
    ("F8", check_problems),
    ("F9", check_runbooks),
    ("F10", check_finops_a),
    ("F11", check_finops_b),
)


def checks(w: Window) -> None:
    for feature, fn in CHECKS:
        _check(w, feature, fn)


def shutdown(w: Window) -> None:
    for comando in (["apps", "stop", APP_NAME], ["warehouses", "stop", w.config.warehouse_id]):
        try:
            w.cli.run(comando)
        except (CommandFailed, QuotaRefused) as exc:
            w.state.notes.append(f"não foi possível executar `{' '.join(comando)}`: {exc}")


STEPS: tuple[Step, ...] = (
    Step("precheck", 0, 0, precheck, always=True),
    Step("deploy", 0, 0, deploy),
    Step("light_run_1", 1, 5, light_run),
    Step("wait_sla", 0, 0, wait_sla),
    Step("cycle_partial", 1, 11, cycle_partial),
    Step("app_deploy", 0, 0, app_deploy),
    Step("manual_ack", 0, 0, manual_ack),
    Step("light_run_2", 1, 5, light_run),
    Step("cycle_full", 1, 13, cycle_full),
)


def execute(w: Window, steps: tuple[Step, ...] = STEPS) -> str:
    """Roda a janela. Devolve o desfecho: concluida, orcamento, recusa ou falha."""
    desfecho = "concluida"
    try:
        for step in steps:
            if step.step_id in w.state.done and not step.always:
                continue
            if not w.budget.fits(w.state, step):
                desfecho = "orcamento"
                w.state.notes.append(
                    f"orçamento: {step.step_id} prevê {step.predicted_min:.0f} min e {step.runs} run(s); "
                    f"consumido {w.state.minutes:.1f}/{w.budget.max_minutes:.0f} min, "
                    f"{w.state.runs}/{w.budget.max_runs} runs"
                )
                break
            inicio = w.clock()
            step.action(w)
            gasto = (w.clock() - inicio) / 60
            if step.runs:
                w.state.minutes += gasto
                w.state.runs += step.runs
            w.state.steps[step.step_id] = {"predicted_min": step.predicted_min, "actual_min": round(gasto, 1)}
            if not step.always:
                w.state.done.append(step.step_id)
    except QuotaRefused as exc:
        w.state.notes.append(f"recusa de cota: {exc}")
        desfecho = "recusa"
    except (CommandFailed, ValueError) as exc:
        w.state.notes.append(f"falha: {exc}")
        desfecho = "falha"
    finally:
        if desfecho != "recusa":
            try:
                checks(w)
            except QuotaRefused as exc:
                w.state.notes.append(f"recusa de cota durante as checagens: {exc}")
        shutdown(w)
    return desfecho


def report(state: State, outcome: str, budget: Budget, now: datetime) -> str:
    linhas = [
        "# Relatório da janela de verificação",
        "",
        f"Gerado por `demo/verify_pending.py` em {now:%Y-%m-%d %H:%M} UTC · janela iniciada em "
        f"{state.started:%Y-%m-%d %H:%M} UTC · desfecho: **{outcome}**",
        "",
        f"Consumo: **{state.minutes:.1f} min** de job em **{state.runs} run(s)** "
        f"(orçamento {budget.max_minutes:.0f} min, {budget.max_runs} runs).",
        "",
        "| Feature | Estado | Detalhe |",
        "|---------|--------|---------|",
    ]
    for chave, nome in FEATURES.items():
        item = state.features.get(chave, {"status": NAO_ALCANCADO, "detail": ""})
        linhas.append(f"| {chave} {nome} | {item['status']} | {item['detail']} |")
    linhas += ["", "| Passo | Previsto (min) | Real (min) |", "|-------|----------------|------------|"]
    for passo, medida in state.steps.items():
        linhas.append(f"| {passo} | {medida['predicted_min']:.0f} | {medida['actual_min']:.1f} |")
    linhas += [
        "",
        "Fora da janela: medição de 14 dias da FinOps B; eficácia de 30 dias (problemas) e de 24 h (runbooks).",
    ]
    if state.notes:
        linhas += ["", "## Notas", "", *[f"- {nota}" for nota in state.notes]]
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="descarta o progresso e começa outra janela")
    parser.add_argument("--no-manual", action="store_true", help="pula o passo manual no console")
    parser.add_argument("--skip-precheck", action="store_true", help="não consulta o status do App e do warehouse")
    args = parser.parse_args(argv)
    profile = os.environ.get("PROFILE")
    warehouse = os.environ.get("WAREHOUSE_ID")
    if not profile or not warehouse:
        print("defina PROFILE e WAREHOUSE_ID", file=sys.stderr)
        return 2
    agora = datetime.now(UTC)
    estado = load_state(STATE_FILE, agora, args.reset)
    orcamento = Budget(float(os.environ.get("BUDGET_MINUTES", 45)), int(os.environ.get("BUDGET_RUNS", 8)))
    config = Config(
        warehouse_id=warehouse,
        catalog=os.environ.get("CATALOG", "workspace"),
        workload_repo=os.environ.get("WORKLOAD_REPO", ""),
        sla_wait_min=float(os.environ.get("SLA_WAIT_MIN", 8)),
        manual=not args.no_manual,
        precheck=not args.skip_precheck,
    )
    janela = Window(Cli(profile), config, estado, orcamento)
    desfecho = execute(janela)
    save_state(STATE_FILE, estado)
    REPORT_FILE.write_text(report(estado, desfecho, orcamento, datetime.now(UTC)), encoding="utf-8")
    print(f"desfecho: {desfecho} · relatório em {REPORT_FILE.relative_to(ROOT)}")
    return 0 if desfecho == "concluida" else 1


if __name__ == "__main__":
    raise SystemExit(main())
