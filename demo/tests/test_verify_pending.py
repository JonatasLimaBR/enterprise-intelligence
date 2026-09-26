"""Janela de verificação com CLI simulado (AT-07…13, SC3…SC7)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_pending as vp  # noqa: E402

AGORA = datetime(2026, 9, 26, 12, tzinfo=UTC)
BLOQUEIO_APP = json.dumps(
    {"compute_status": {"state": "STOPPED", "message": "App compute was stopped due to workspace or account status."}}
)
RECUSA_RUN = (
    "Error: cannot start job: Triggering new runs for organization 7474644308924051 is currently disabled temporarily."
)


class FakeCli:
    """Responde por trecho do comando; registra tudo o que foi chamado."""

    def __init__(self, responses: dict[str, str] | None = None, rows: dict[str, list[dict]] | None = None):
        self.calls: list[list[str]] = []
        self.responses = responses or {}
        self.rows = rows or {}

    def __call__(self, command: list[str], cwd: Path | None) -> tuple[int, str]:
        self.calls.append(command)
        texto = " ".join(command)
        if "aitools tools query" in texto:
            for trecho, linhas in self.rows.items():
                if trecho in texto:
                    return 0, json.dumps(linhas)
            return 0, "[]"
        for trecho, saida in self.responses.items():
            if trecho in texto:
                return (1 if saida.startswith("ERRO") else 0), saida
        return 0, "{}"

    def ran(self, trecho: str) -> list[str]:
        return [" ".join(chamada) for chamada in self.calls if trecho in " ".join(chamada)]


class Relogio:
    def __init__(self, minutos_por_chamada: float = 5.0):
        self.t = 0.0
        self.passo = minutos_por_chamada * 60

    def __call__(self) -> float:
        self.t += self.passo / 2
        return self.t


def _janela(fake: FakeCli, estado: vp.State | None = None, budget: vp.Budget | None = None, manual=True,
            precheck=True, respostas_manual: list[str] | None = None, clock=None):
    perguntas = respostas_manual if respostas_manual is not None else []
    return vp.Window(
        vp.Cli("eict", runner=fake),
        vp.Config("6836da016907f9bc", manual=manual, precheck=precheck),
        estado or vp.State(AGORA.isoformat()),
        budget or vp.Budget(),
        wait=lambda segundos: None,
        ask=lambda texto: perguntas.append(texto) or "",
        clock=clock or Relogio(),
        audit_verify=lambda linhas: type("V", (), {"status": "integra", "detail": ""})(),
    )


def test_at07_sc3_app_parado_pela_conta_aborta_sem_disparar_nada():
    fake = FakeCli({"apps get": BLOQUEIO_APP})
    janela = _janela(fake)
    assert vp.execute(janela) == "recusa"
    assert fake.ran("bundle run") == []
    assert fake.ran("bundle deploy") == []
    assert "skip-precheck" in janela.state.notes[0]


def test_skip_precheck_nao_consulta_o_app():
    fake = FakeCli({"apps get": BLOQUEIO_APP})
    vp.execute(_janela(fake, precheck=False))
    assert fake.ran("apps get") == []


def test_janela_completa_usa_4_runs_e_nunca_o_job_grande():
    fake = FakeCli()
    janela = _janela(fake)
    assert vp.execute(janela) == "concluida"
    runs = fake.ran("bundle run")
    assert len([run for run in runs if "sales_daily_small" in run or "eict_cycle" in run]) == 4
    assert all("sales_daily " not in f"{run} " for run in runs)
    assert janela.state.runs == 4
    assert any(f"stages={vp.PARTIAL_STAGES}" in run for run in runs)


def test_at13_allowlist_recusa_o_job_grande_antes_do_subprocess():
    fake = FakeCli()
    with pytest.raises(ValueError, match="allowlist"):
        vp.Cli("eict", runner=fake).bundle_run("sales_daily", vp.WORKLOAD, "warehouse_id=x")
    assert fake.calls == []


def test_at08_sc4_orcamento_insuficiente_para_antes_do_passo():
    fake = FakeCli()
    estado = vp.State(AGORA.isoformat(), minutes=41.0, runs=1)
    janela = _janela(fake, estado)
    assert vp.execute(janela) == "orcamento"
    assert fake.ran("bundle run") == []
    assert "orçamento" in janela.state.notes[0]
    assert janela.state.done == ["deploy"]


def test_orcamento_de_runs_tambem_para():
    janela = _janela(FakeCli(), budget=vp.Budget(max_minutes=999, max_runs=1))
    assert vp.execute(janela) == "orcamento"
    assert janela.state.runs == 1


def test_at09_recusa_no_meio_para_deixa_o_passo_pendente_e_desliga():
    fake = FakeCli({"eict_cycle": RECUSA_RUN})
    janela = _janela(fake)
    assert vp.execute(janela) == "recusa"
    assert "cycle_partial" not in janela.state.done
    assert janela.state.done[-1] == "wait_sla"
    assert fake.ran("apps stop") and fake.ran("warehouses stop")
    assert fake.ran("aitools tools query") == []


def test_at10_sc5_retomada_pula_o_que_ja_foi_feito():
    fake = FakeCli()
    estado = vp.State(AGORA.isoformat(), done=["deploy", "light_run_1", "wait_sla"], minutes=5.0, runs=1)
    vp.execute(_janela(fake, estado))
    assert fake.ran("bundle deploy") == []
    primeiro_run = fake.ran("bundle run")[0]
    assert "eict_cycle" in primeiro_run and "stages=" in primeiro_run


def test_sc7_desliga_app_e_warehouse_em_todos_os_desfechos():
    for fake, estado in (
        (FakeCli(), None),
        (FakeCli(), vp.State(AGORA.isoformat(), minutes=44.0)),
        (FakeCli({"eict_cycle": RECUSA_RUN}), None),
        (FakeCli({"bundle deploy": "ERRO: bundle inválido"}), None),
    ):
        vp.execute(_janela(fake, estado))
        assert fake.ran("apps stop") and fake.ran("warehouses stop")


def test_falha_de_comando_para_a_janela_mas_checa_o_que_ha():
    fake = FakeCli({"bundle deploy": "ERRO: bundle inválido"})
    janela = _janela(fake)
    assert vp.execute(janela) == "falha"
    assert fake.ran("aitools tools query")


def test_desligar_recusado_vira_nota_nao_erro():
    fake = FakeCli({"apps stop": "ERRO: app já parado", "warehouses stop": RECUSA_RUN})
    janela = _janela(fake)
    vp.execute(janela)
    assert len([nota for nota in janela.state.notes if "não foi possível" in nota]) == 2


def _linhas_verificacao(sla="inc-sla", estado_sla="recovered"):
    desde = (AGORA + timedelta(minutes=1)).isoformat()
    return {
        "incident_runbooks": [{"n": 1}],
        "type = 'sla_risk'": [{"incident_id": sla}],
        f"WHERE incident_id = '{sla}'": [{"state": estado_sla}],
        "sla_predictions": [{"n": 2}],
        "ORDER BY seq": [{"seq": 1, "at": desde, "action": "acknowledge_incident"}],
        "connector_health": [{"connector": "databricks_jobs", "status": "saudavel"}],
        "metric_id = 'incremental_cost_usd'": [{"n": 1}],
        "count(DISTINCT metric_id)": [{"n": 14}],
        "acknowledged_at >=": [{"n": 1}],
        "action = 'acknowledge_incident'": [{"n": 1}],
        "recommendations": [{"n": 3}],
        "DESCRIBE HISTORY": [{"timestamp": desde}],
        "ops.runbooks": [{"n": 9}],
        "cost_reconciliation": [{"period_label": "2026-08", "reconciled": True, "total_billing": 10},
                                {"period_label": "2026-09", "reconciled": True, "total_billing": 10}],
        "cost_allocation": [{"c": 2}],
        "savings_detectors": [{"source": s, "status": "avaliado", "reason": ""} for s in
                              ("regressao_custo", "execucao_falhada", "schedule_fora_prod")]
        + [{"source": "warehouse_ocioso", "status": "nao_avaliado", "reason": "query.history indisponível"}],
    }


def test_sc6_relatorio_traz_as_11_features_verificadas():
    fake = FakeCli(rows=_linhas_verificacao())
    janela = _janela(fake, respostas_manual=[])
    assert vp.execute(janela) == "concluida"
    estados = {chave: item["status"] for chave, item in janela.state.features.items()}
    assert estados == {chave: vp.VERIFICADO for chave in vp.FEATURES}
    assert "10.0%" in janela.state.features["F10"]["detail"]
    assert "nao_avaliado" in janela.state.features["F11"]["detail"]
    texto = vp.report(janela.state, "concluida", vp.Budget(), AGORA)
    assert all(nome in texto for nome in vp.FEATURES.values())
    assert "4 run(s)" in texto


def test_sla_que_nao_recupera_falha_com_motivo():
    fake = FakeCli(rows=_linhas_verificacao(estado_sla="detected"))
    janela = _janela(fake)
    vp.execute(janela)
    assert janela.state.features["F1"]["status"] == vp.FALHOU
    assert "detected" in janela.state.features["F1"]["detail"]


def test_at11_confirmar_sem_ter_feito_falha_na_checagem():
    linhas = _linhas_verificacao()
    linhas["acknowledged_at >="] = [{"n": 0}]
    janela = _janela(FakeCli(rows=linhas))
    vp.execute(janela)
    assert janela.state.features["F6"]["status"] == vp.FALHOU


def test_passo_manual_mostra_o_incidente_de_sla():
    perguntas: list[str] = []
    vp.execute(_janela(FakeCli(rows=_linhas_verificacao()), respostas_manual=perguntas))
    assert len(perguntas) == 1 and "inc-sla" in perguntas[0]


def test_no_manual_marca_f2_e_f6_nao_alcancadas():
    janela = _janela(FakeCli(rows=_linhas_verificacao()), manual=False)
    vp.execute(janela)
    assert janela.state.features["F2"]["status"] == vp.NAO_ALCANCADO
    assert janela.state.features["F6"]["status"] == vp.NAO_ALCANCADO


def test_feature_nao_checada_aparece_como_nao_alcancada_no_relatorio():
    texto = vp.report(vp.State(AGORA.isoformat()), "recusa", vp.Budget(), AGORA)
    assert texto.count(vp.NAO_ALCANCADO) == len(vp.FEATURES)


def test_estado_com_mais_de_24h_exige_reset(tmp_path):
    arquivo = tmp_path / "estado.json"
    vp.save_state(arquivo, vp.State((AGORA - timedelta(hours=25)).isoformat()))
    with pytest.raises(SystemExit, match="--reset"):
        vp.load_state(arquivo, AGORA, reset=False)
    assert vp.load_state(arquivo, AGORA, reset=True).done == []


def test_estado_ida_e_volta(tmp_path):
    arquivo = tmp_path / "estado.json"
    estado = vp.State(AGORA.isoformat(), done=["deploy"], minutes=3.5, runs=1, sla_incident_id="inc-1")
    vp.save_state(arquivo, estado)
    assert vp.load_state(arquivo, AGORA, reset=False) == estado


def test_parse_time_aceita_os_formatos_do_cli():
    assert vp.parse_time("2026-09-26T12:00:00.000Z") == AGORA
    assert vp.parse_time("2026-09-26 12:00:00") == AGORA
    assert vp.parse_time("lixo") is None


def test_verificacao_real_da_auditoria_converte_o_instante():
    sys.path.insert(0, str(vp.PLATFORM / "app"))
    from audit import GENESIS, entry

    linha = entry(None, AGORA, "a@x", frozenset({"finops"}), "approve_saving", "opp-1", "allowed", "")
    assert linha["prev_hash"] == GENESIS
    como_cli = {**linha, "at": "2026-09-26T12:00:00.000Z"}
    assert vp._audit_verify([como_cli]).status == "integra"


def test_scripts_bash_sao_sintaticamente_validos():
    for nome in ("verify_pending.sh", "start_demo.sh", "stop_demo.sh", "trigger_recorrencia.sh"):
        resultado = subprocess.run(["bash", "-n", str(vp.HERE / nome)], capture_output=True, text=True)
        assert resultado.returncode == 0, f"{nome}: {resultado.stderr}"


def test_at15_fato_de_consumo_so_existe_com_medicao(tmp_path):
    import build_numbers

    assert build_numbers.presentation_facts(tmp_path / "ausente.json") == {}
    arquivo = tmp_path / "custo.json"
    arquivo.write_text('{"seconds": 780, "runs": 2, "measured_at": "2026-09-26T12:00:00Z", '
                       '"stages": "collect,medallion,correlate,narrate"}', encoding="utf-8")
    fato = build_numbers.presentation_facts(arquivo)["presentation_compute_min"]
    assert fato["value"] == 13
    assert "trigger_recorrencia.sh" in fato["source"] and "2026-09-26" in fato["source"]
