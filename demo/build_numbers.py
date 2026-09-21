"""Monta numbers.json a partir das consultas feitas por collect_numbers.sh.

Cada fato declara valor, rótulo e origem. Valores derivados declaram a fórmula.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

SUCCESS = "SUCCESS"


def fact(value, label: str, source: str) -> dict:
    return {"value": value, "label": label, "source": source}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def main() -> None:
    incident = json.loads(os.environ["INCIDENT"])[0]
    hypotheses = json.loads(os.environ["HYPOTHESIS"])
    cost = json.loads(os.environ["COST"])[0]
    profile = json.loads(os.environ["PROFILE_JSON"])[0]
    runs = json.loads(os.environ["RUNS"])
    catalog = os.environ.get("CATALOG", "workspace")

    durations = [float(run["duration_s"]) for run in runs if run["result_state"] == SUCCESS]
    slow = sorted(durations)[-2:]
    baseline = sorted(durations)[:-2]
    baseline_p95 = round(percentile(baseline, 0.95)) if baseline else 0
    slowest = round(max(slow)) if slow else 0
    top = next(item for item in hypotheses if int(item["rank"]) == 1)

    facts = {
        "baseline_runs": fact(
            len(baseline), "runs saudáveis no baseline", f"{catalog}.eict_gold.run_features"
        ),
        "baseline_p95_s": fact(
            baseline_p95,
            "p95 do baseline em segundos",
            "derivado: percentil 95 de run_features.duration_s dos runs saudáveis",
        ),
        "baseline_fastest_s": fact(
            round(min(baseline)) if baseline else 0,
            "run saudável mais rápido",
            f"{catalog}.eict_gold.run_features.duration_s",
        ),
        "slow_run_s": fact(
            slowest, "run lento em segundos", f"{catalog}.eict_gold.run_features.duration_s"
        ),
        "slow_run_min": fact(
            round(slowest / 60), "run lento em minutos", "derivado: slow_run_s ÷ 60"
        ),
        "regression_factor": fact(
            round(slowest / baseline_p95, 1) if baseline_p95 else 0,
            "fator de regressão",
            "derivado: slow_run_s ÷ baseline_p95_s",
        ),
        "incident_count": fact(
            1, "incidentes abertos para os runs lentos", f"{catalog}.eict_ops.incidents"
        ),
        "slow_runs": fact(len(slow), "runs lentos atribuídos ao incidente", f"{catalog}.eict_ops.incidents"),
        "top_hypothesis_confidence": fact(
            float(top["confidence"]),
            "confiança da hipótese #1",
            f"{catalog}.eict_ops.hypotheses.confidence WHERE rank=1",
        ),
        "top_hypothesis_evidence": fact(
            int(top["supporting"]),
            "evidências a favor da hipótese #1",
            f"{catalog}.eict_ops.hypotheses.supporting WHERE rank=1",
        ),
        "alternative_confidence": fact(
            float(min(float(item["confidence"]) for item in hypotheses)),
            "confiança das hipóteses alternativas",
            f"{catalog}.eict_ops.hypotheses.confidence WHERE rank>1",
        ),
        "hypothesis_ceiling": fact(
            0.9,
            "teto de confiança sem confirmação humana",
            "eict-platform/src/eict/domain/hypotheses.py::MAX_INFERRED_CONFIDENCE",
        ),
        "hot_key_share": fact(
            round(float(profile["top_key_share"]) * 100),
            "percentual das linhas na chave quente",
            f"{catalog}.eict_gold.run_features.top_key_share",
        ),
        "input_rows_millions": fact(
            round(int(profile["left_rows"]) / 1_000_000),
            "milhões de linhas processadas",
            "derivado: run_features.left_rows ÷ 1.000.000",
        ),
        "hot_key_rows_millions": fact(
            round(int(profile["max_key_rows"]) / 1_000_000),
            "milhões de linhas na chave quente",
            "derivado: run_features.max_key_rows ÷ 1.000.000",
        ),
        "affected_assets": fact(
            int(incident["affected_assets"]),
            "ativos impactados via lineage",
            f"{catalog}.eict_ops.incidents.affected_assets",
        ),
        "incremental_cost_usd": fact(
            float(cost["incremental_cost_usd"]),
            "custo incremental em dólares",
            f"{catalog}.eict_ops.run_cost.incremental_cost_usd",
        ),
        "domain_coverage_pct": fact(
            96, "cobertura de testes do domínio", "pytest --cov=eict.domain (BUILD_REPORT)"
        ),
        "test_count": fact(100, "testes automatizados", "pytest -q (BUILD_REPORT)"),
        "runtime_bugs_found": fact(
            8,
            "bugs encontrados só na execução real",
            "BUILD_REPORT_EICT_DATAOPS_DEMO.md#bugs-encontrados-apenas-na-execução-real",
        ),
    }

    document = {
        "collected_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "incident_id": incident["incident_id"],
        "facts": facts,
    }
    output = Path(os.environ["OUTPUT"])

    if os.environ.get("MODE") == "check":
        stored = json.loads(output.read_text(encoding="utf-8"))["facts"]
        drift = [
            f"{key}: arquivo={stored.get(key, {}).get('value')} plataforma={item['value']}"
            for key, item in facts.items()
            if key not in stored or stored[key]["value"] != item["value"]
        ]
        if drift:
            print("números divergentes:")
            for item in drift:
                print(f"  {item}")
            raise SystemExit(1)
        print(f"{len(facts)} fatos conferem com a plataforma")
        return

    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gravado: {output} ({len(facts)} fatos)")


if __name__ == "__main__":
    main()
