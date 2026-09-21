"""Congela o comportamento da chave de correlação antes da generalização.

A feature de contratos troca `job_id` por `subject`. Se a string montada mudar, todo incidente
aberto muda de identidade e a idempotência se perde silenciosamente — por isso o valor fica
travado aqui, calculado à mão a partir da regra documentada.
"""

from __future__ import annotations

import hashlib

from eict.domain.incidents import RUNTIME_REGRESSION, correlation_key, open_or_update
from tests.conftest import JOB_ID, TENANT, make_run

FIRST_RUN_ID = "run-7"


def esperado(tenant: str, subject: str, tipo: str, evento: str) -> str:
    return hashlib.sha256(f"{tenant}|{subject}|{tipo}|{evento}".encode()).hexdigest()[:16]


def test_at018_chave_de_runtime_permanece_identica():
    chave = correlation_key(TENANT, JOB_ID, RUNTIME_REGRESSION, FIRST_RUN_ID)

    assert chave == esperado(TENANT, JOB_ID, RUNTIME_REGRESSION, FIRST_RUN_ID)
    assert len(chave) == 16


def test_chave_muda_quando_o_subject_muda():
    do_job = correlation_key(TENANT, JOB_ID, RUNTIME_REGRESSION, FIRST_RUN_ID)
    de_outro = correlation_key(TENANT, "job-99", RUNTIME_REGRESSION, FIRST_RUN_ID)

    assert do_job != de_outro


def test_chave_muda_quando_o_tipo_muda():
    runtime = correlation_key(TENANT, JOB_ID, RUNTIME_REGRESSION, FIRST_RUN_ID)
    qualidade = correlation_key(TENANT, JOB_ID, "contract_violation", FIRST_RUN_ID)

    assert runtime != qualidade


def test_at011_incidente_de_runtime_continua_agrupando_por_job():
    primeiro = make_run(7, duration_s=3420)
    segundo = make_run(8, duration_s=3500)

    incidente, criado = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, primeiro)
    atualizado, recriado = open_or_update(
        [incidente], TENANT, JOB_ID, RUNTIME_REGRESSION, segundo
    )

    assert criado is True
    assert recriado is False
    assert atualizado.correlation_key == incidente.correlation_key


def test_at012_subjects_diferentes_geram_incidentes_distintos():
    run = make_run(7, duration_s=3420)

    do_job, _ = open_or_update([], TENANT, JOB_ID, RUNTIME_REGRESSION, run)
    de_outro, criado = open_or_update([do_job], TENANT, "job-99", RUNTIME_REGRESSION, run)

    assert criado is True
    assert de_outro.correlation_key != do_job.correlation_key
