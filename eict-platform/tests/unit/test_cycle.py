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
