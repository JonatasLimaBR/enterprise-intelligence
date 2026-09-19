# SPEC-004 — Correlação, Anomalia e RCA

## Pipeline

1. normalizar;
2. resolver identidade do asset;
3. enriquecer com topologia, owner e criticidade;
4. calcular baseline/anomalia;
5. agrupar temporal e topologicamente;
6. correlacionar changes;
7. criar/atualizar incidente;
8. gerar hipóteses;
9. avaliar impacto;
10. recomendar testes/ações.

## Deduplicação

Fingerprint usa tenant, categoria, primary asset, normalized error signature e janela. Alertas upstream podem suprimir children quando há causalidade/topologia forte; filhos continuam como evidência.

## Baseline

Segmentar por workload/version/schedule/weekday/volume band/compute class. Exigir tamanho mínimo de amostra; mostrar incerteza. Winsorization ou robust statistics para outliers; mudanças de regime abrem novo baseline.

## Change correlation

Pontuação considera proximidade temporal, asset overlap, dependency path, tipo de mudança, diff material, histórico e ausência de explicação alternativa. Correlação nunca é confirmada automaticamente sem teste ou revisão.

## RCA output

```json
{
  "facts": [],
  "hypotheses": [{
    "statement": "Data skew introduced by join",
    "confidence": 0.91,
    "supporting_evidence_ids": [],
    "contradicting_evidence_ids": [],
    "missing_evidence": [],
    "tests": []
  }],
  "recommended_actions": [],
  "limitations": []
}
```

## Avaliação

Replay de incidentes conhecidos, cenários sintéticos, precision/recall de correlação, top-k RCA accuracy, calibration error, tempo economizado e revisão cega por especialistas.

