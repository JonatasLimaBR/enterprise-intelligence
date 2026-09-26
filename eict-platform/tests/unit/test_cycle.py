from __future__ import annotations

import pytest

from eict.jobs.cycle import STAGE_FAILED, STAGE_OK, StageResult, run_stage, summarize


def test_etapa_bem_sucedida_registra_duracao():
    resultado = run_stage("collect", lambda: None)

    assert resultado.status == STAGE_OK
    assert resultado.error is None
    assert resultado.seconds >= 0


def test_etapa_que_falha_nao_propaga_a_excecao():
    def explode() -> None:
        raise RuntimeError("jira indisponível")

    resultado = run_stage("dispatch", explode)

    assert resultado.status == STAGE_FAILED
    assert "jira indisponível" in resultado.error


def test_uma_falha_nao_impede_as_demais_etapas():
    executadas: list[str] = []

    def falha() -> None:
        raise RuntimeError("erro")

    resultados = [
        run_stage("quality", lambda: executadas.append("quality")),
        run_stage("correlate", falha),
        run_stage("narrate", lambda: executadas.append("narrate")),
    ]

    assert executadas == ["quality", "narrate"]
    assert [item.status for item in resultados] == [STAGE_OK, STAGE_FAILED, STAGE_OK]


def test_resumo_conta_etapas_e_tempo():
    resultados = [
        StageResult("bootstrap", STAGE_OK, 1.5),
        StageResult("collect", STAGE_FAILED, 0.5, "sem rede"),
    ]

    texto = summarize(resultados)

    assert "1/2 etapas ok" in texto
    assert "2.0s" in texto
    assert "sem rede" in texto


def test_mensagem_da_etapa_e_legivel():
    assert str(StageResult("quality", STAGE_OK, 3.25)) == "quality: ok em 3.2s"


def test_ciclo_falha_no_final_quando_alguma_etapa_falhou():
    from eict.jobs.cycle import run_all

    with pytest.raises(SystemExit, match="correlate"):
        run_all([("quality", lambda: None), ("correlate", _erro)])


def test_ciclo_sem_falhas_termina_sem_erro():
    from eict.jobs.cycle import run_all

    run_all([("quality", lambda: None)])


def test_as_etapas_cobrem_o_ciclo_inteiro_na_ordem_de_dependencia():
    from eict.jobs.cycle import cycle_stages

    nomes = [nome for nome, _ in cycle_stages(None)]

    assert nomes == [
        "bootstrap",
        "collect",
        "medallion",
        "quality",
        "semantics",
        "correlate",
        "narrate",
        "dispatch",
    ]


def test_pipeline_sem_id_e_ignorado_sem_erro():
    from eict.jobs.cycle import run_pipeline

    run_pipeline("")


def test_pipeline_id_vem_dos_parametros():
    from eict.jobs.cycle import pipeline_id_from

    assert pipeline_id_from(["--catalog=workspace", "--pipeline-id=abc-123"]) == "abc-123"
    assert pipeline_id_from(["--catalog=workspace"]) == ""


def _erro() -> None:
    raise RuntimeError("correlator quebrou")


def _etapas(chamadas: list[str]):
    return [(nome, (lambda nome=nome: chamadas.append(nome))) for nome in ("bootstrap", "collect", "correlate")]


def test_at01_so_as_etapas_pedidas_rodam_e_as_demais_ficam_puladas():
    from eict.jobs.cycle import STAGE_SKIPPED, select_stages

    chamadas: list[str] = []
    resultados = [run_stage(nome, acao) for nome, acao in select_stages(_etapas(chamadas), "bootstrap")]
    assert chamadas == ["bootstrap"]
    assert [item.status for item in resultados] == [STAGE_OK, STAGE_SKIPPED, STAGE_SKIPPED]
    assert resultados[1].error == "não selecionada"


def test_at02_ordem_e_a_do_ciclo_nao_a_digitada():
    from eict.jobs.cycle import select_stages

    chamadas: list[str] = []
    for nome, acao in select_stages(_etapas(chamadas), "correlate, collect"):
        run_stage(nome, acao)
    assert chamadas == ["collect", "correlate"]


def test_at03_etapa_desconhecida_falha_antes_de_rodar_qualquer_uma():
    from eict.jobs.cycle import select_stages

    chamadas: list[str] = []
    with pytest.raises(ValueError, match="xyz"):
        select_stages(_etapas(chamadas), "bootstrap,xyz")
    assert chamadas == []


def test_all_ou_vazio_roda_tudo():
    from eict.jobs.cycle import select_stages

    etapas = _etapas([])
    assert select_stages(etapas, "all") is etapas
    assert select_stages(etapas, "") is etapas


def test_at04_sem_observacao_nova_o_pipeline_fica_pulado(monkeypatch):
    from eict.jobs import cycle

    disparos: list[str] = []
    monkeypatch.setattr(cycle, "run_pipeline", disparos.append)
    resultado = run_stage("medallion", lambda: cycle.medallion_stage(cycle.CycleContext(inserted=0), "p1"))
    assert (resultado.status, resultado.error) == (cycle.STAGE_SKIPPED, "sem eventos novos")
    assert disparos == []


def test_com_observacao_nova_o_pipeline_roda(monkeypatch):
    from eict.jobs import cycle

    disparos: list[str] = []
    monkeypatch.setattr(cycle, "run_pipeline", disparos.append)
    cycle.medallion_stage(cycle.CycleContext(inserted=3), "p1")
    assert disparos == ["p1"]


def test_at05_force_pipeline_roda_mesmo_sem_observacao(monkeypatch):
    from eict.jobs import cycle

    disparos: list[str] = []
    monkeypatch.setattr(cycle, "run_pipeline", disparos.append)
    cycle.medallion_stage(cycle.CycleContext(force_pipeline=True, inserted=0), "p1")
    assert disparos == ["p1"]


def test_at06_sem_contagem_o_pipeline_roda(monkeypatch):
    from eict.jobs import cycle

    disparos: list[str] = []
    monkeypatch.setattr(cycle, "run_pipeline", disparos.append)
    cycle.medallion_stage(cycle.CycleContext(), "p1")
    assert disparos == ["p1"]


def test_resumo_conta_puladas_a_parte():
    from eict.jobs.cycle import STAGE_SKIPPED

    texto = summarize([StageResult("bootstrap", STAGE_OK, 1.0), StageResult("medallion", STAGE_SKIPPED, 0.0, "x")])
    assert "1/2 etapas ok, 1 pulada(s)" in texto


def test_pulada_nao_derruba_o_ciclo():
    from eict.jobs.cycle import run_all, select_stages

    run_all(select_stages([("bootstrap", lambda: None), ("collect", _erro)], "bootstrap"))


def test_parametros_de_etapas_e_force():
    from eict.jobs.cycle import stages_from

    assert stages_from(["--stages=bootstrap,collect", "--force-pipeline=true"]) == ("bootstrap,collect", True)
    assert stages_from([]) == ("all", False)
