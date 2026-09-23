"""Divergência semântica vira incidente — e só fecha com extração completa que passou.

O caso central usa o código real do workload: `sales_daily.py` e `sales_daily_small.py`
calculam `revenue` de formas diferentes, e isso tem que chegar à fila com as duas
fórmulas em evidência e o raio até o painel.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from eict.domain.extraction import extract
from eict.domain.impact import Edge
from eict.domain.incidents import SEMANTIC_CONFLICT
from eict.domain.metrics import (
    FORMULA_CONFLICT,
    SYNONYM,
    Divergence,
    compare,
)
from eict.domain.semantic_incidents import evaluated_assets, group_conflicts
from eict.jobs.correlate_quality import QualityInput, SemanticInput, correlate_quality

NOW = datetime(2026, 9, 23, 10, tzinfo=UTC)
TENANT = "demo"
SALES = "workspace.eict_workload.sales_daily"
WORKLOAD = Path(__file__).resolve().parents[3] / "eict-demo-workload" / "src"
GRANDE = "eict-demo-workload/src/sales_daily.py"
PEQUENO = "eict-demo-workload/src/sales_daily_small.py"
SOURCES = ((GRANDE, SALES), (PEQUENO, SALES))


def _observadas(*paths: str) -> list:
    saida: list = []
    for path in paths:
        codigo = (WORKLOAD / Path(path).name).read_text(encoding="utf-8")
        saida.extend(extract(codigo, path, SALES))
    return saida


def _semantica(observadas, sources=SOURCES) -> SemanticInput:
    return SemanticInput(
        observed=observadas, sources=sources, divergences=compare([], observadas)
    )


def _payload(semantics: SemanticInput | None, graph=()) -> QualityInput:
    return QualityInput(
        results=[], contracts={}, changes=[], producer_states={}, graph=graph, semantics=semantics
    )


def _painel() -> Edge:
    return Edge(source=SALES, target="", entity_type="DASHBOARD_V3", entity_id="painel", last_seen=NOW)


def test_at10_conflito_real_abre_incidente_com_as_duas_formulas_e_o_raio():
    touched, entries, evidences, _ = correlate_quality(
        _payload(_semantica(_observadas(GRANDE, PEQUENO)), graph=(_painel(),)), [], TENANT, NOW
    )

    incidente = next(item for item in touched if item.type == SEMANTIC_CONFLICT)
    assert incidente.subject == SALES
    assert incidente.severity == "critical"
    assert incidente.escalated_from == "warning"

    conflito = next(
        json.loads(item.value)
        for incident_id, item in evidences
        if incident_id == incidente.incident_id and '"formula_conflict"' in item.value
    )
    assert conflito["metric_id"] == "revenue"
    assert {fonte["path"] for fonte in conflito["sources"]} == {GRANDE, PEQUENO}
    assert all(fonte["line"] > 0 and fonte["formula"] for fonte in conflito["sources"])
    assert any(entry.kind == "detected" for entry in entries)


def test_divergencia_nao_bloqueante_nao_abre_incidente():
    sinonimo = Divergence(kind=SYNONYM, metric_id="a", asset=SALES, detail="a e b")

    assert group_conflicts([sinonimo]) == {}


def test_sem_extracao_nada_semantico_abre_nem_fecha():
    abertos = correlate_quality(
        _payload(_semantica(_observadas(GRANDE, PEQUENO))), [], TENANT, NOW
    )[0]

    touched, _, _, _ = correlate_quality(_payload(None), abertos, TENANT, NOW)

    assert touched == []


def test_conflito_corrigido_fecha_no_ciclo_seguinte():
    abertos = correlate_quality(
        _payload(_semantica(_observadas(GRANDE, PEQUENO))), [], TENANT, NOW
    )[0]
    corrigidas = [
        replace(item, source_path=PEQUENO) for item in _observadas(GRANDE)
    ] + _observadas(GRANDE)

    touched, entries, _, _ = correlate_quality(
        _payload(_semantica(corrigidas)), abertos, TENANT, NOW
    )

    assert [item.state for item in touched if item.type == SEMANTIC_CONFLICT] == ["recovered"]
    assert any(entry.kind == "auto_resolved" for entry in entries)


def test_busca_parcial_nao_fecha_o_conflito():
    """Um dos dois arquivos não foi lido: o conflito some por falta de evidência, não por conserto."""
    abertos = correlate_quality(
        _payload(_semantica(_observadas(GRANDE, PEQUENO))), [], TENANT, NOW
    )[0]

    touched, _, _, _ = correlate_quality(
        _payload(_semantica(_observadas(GRANDE))), abertos, TENANT, NOW
    )

    assert all(item.state != "recovered" for item in touched)


def test_avaliado_exige_todos_os_arquivos_do_ativo():
    assert evaluated_assets(_observadas(GRANDE), SOURCES) == frozenset()
    assert evaluated_assets(_observadas(GRANDE, PEQUENO), SOURCES) == {SALES}


def test_conflito_persistente_atualiza_o_mesmo_incidente():
    semantica = _semantica(_observadas(GRANDE, PEQUENO))
    primeiro = correlate_quality(_payload(semantica), [], TENANT, NOW)[0]

    segundo, entries, _, _ = correlate_quality(_payload(semantica), primeiro, TENANT, NOW)

    assert [item.incident_id for item in segundo] == [primeiro[0].incident_id]
    assert [entry.kind for entry in entries] == ["recurrence"]


def test_o_conflito_real_e_de_formula():
    divergencias = group_conflicts(compare([], _observadas(GRANDE, PEQUENO)))

    assert FORMULA_CONFLICT in {item.kind for item in divergencias[SALES]}


def test_registry_padrao_e_o_do_bundle_e_nao_depende_do_diretorio_de_trabalho(monkeypatch, tmp_path):
    from eict.config import Settings
    from eict.jobs.semantics import metrics_dir

    monkeypatch.chdir(tmp_path)

    assert (metrics_dir(Settings()) / "registry.yaml").exists()
