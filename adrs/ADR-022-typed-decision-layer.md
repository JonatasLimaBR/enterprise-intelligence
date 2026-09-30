# ADR-022 — Camada de decisão tipada (Jev) como recomendação, nunca autoridade

Status: aceita para desenho. Implementada em `EICT_JEV_ADVISOR` (2026-09-30).

## Decisão
Um modelo de decisão tipada (Jev/TypeSafe System One, ou equivalente) entra no EICT **apenas como camada de
recomendação/triagem** em zonas cinzentas — recomenda, nunca autoriza nem bloqueia. A autoridade continua
determinística: policy engine (ADR-007) e review humano. Regras vinculantes:

1. **Recomenda, não decide.** A saída vira `Recommendation` (origem "jev") em `ops.recommendations`, sujeita
   a review humano; nunca é executada nem trava um gate.
2. **Não é evidência.** `evidence_ids` vazio; a recomendação é inferência rotulada ("Jev (IA)"), não fato
   citável (preserva ADR-005, evidência antes de inferência).
3. **Egress mínimo e desligado por padrão.** Só sai um `state` de campos em **allow-list definida em código**
   (não ampliável por config); nunca PII, segredo, evidência crua ou patch. Exige opt-in explícito
   (`jev/advisors.yaml` habilitado) **e** credencial (`jev_api_key`); sem qualquer um, nenhuma chamada
   externa (ADR-012, privacidade/retenção).
4. **Confiança é triagem, não veredito.** A probabilidade calibrada do modelo **não** reflete
   necessariamente a precisão (observado ~45% de acerto a 0,74 de confiança quando havia regra desconhecida).
   Um limiar (0,70) filtra o que vira recomendação, mas a taxa de aceitação humana é o detector de
   descalibração (KPI), não a confiança auto-reportada.
5. **Fora do caminho determinístico que vira policy.** Scores que alimentam decisões vinculantes
   (change risk → gates, severidade, backoff) permanecem determinísticos e reprodutíveis; o modelo tipado
   não os substitui.

## Motivação
Modelos de decisão tipada ("System One") são baratos e rápidos e cabem onde "um LLM faz trabalho de `if`".
O EICT, porém, mantém as decisões determinísticas e usa LLM só para **escrever** (narrador) — cuja saída já
é validada e tem fallback. O ganho real do modelo tipado está nas **zonas cinzentas** que o determinístico
não resolve bem (triagem de incidente de severidade média, erro de conector ambíguo, empate de runbook),
desde que entre sem violar os princípios não-negociáveis. Os quatro padrões da categoria — rotear, filtrar,
pontuar, liberar — mapeiam assim no EICT: **filtrar/liberar** têm papel no futuro action gateway (feature 4)
como *triador* "auto/confirmar/humano" sob policy determinística; **pontuar** é evitado (nossos scores viram
policy e precisam ser reprodutíveis); **rotear** é marginal.

## Alternativas
- Deixar o modelo tipado **autorizar/bloquear** ações ou gates: rejeitado — quebra ADR-007 e a
  reprodutibilidade; confiança ≠ precisão.
- Substituir scores determinísticos (change risk, impacto) por nota do modelo: rejeitado — perde
  reprodutibilidade e auditabilidade.
- Enviar estado completo do incidente/erro para mais contexto: rejeitado — vazaria PII/segredo.
- Usar o LLM narrador para essas decisões: rejeitado — texto não determinístico; já rejeitado na validação.

## Consequências
Recomendações do modelo convivem com as determinísticas em `ops.recommendations`, distinguidas por `kind`
e rótulo. Egress externo e credencial tornam a verificação real diferida (como ITSM/Jira). O contrato da API
é isolado num adapter com fake, para ajuste num só lugar quando a API real for confirmada. É preciso medir a
calibração (aceitação humana) para ajustar limiar/uso — descalibração silenciosa é o principal risco. No
action gateway (feature 4), o modelo tipado poderá triar, mas a liberação é sempre da policy.
