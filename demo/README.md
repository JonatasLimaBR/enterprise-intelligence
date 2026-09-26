# Kit de demonstração

Tudo que é preciso para mostrar a EICT funcionando — ao vivo, em vídeo, no GitHub ou numa
entrevista técnica. O estado da demo é real e restaurável em segundos.

## Qual arquivo para qual situação

| Situação | Comece por |
|----------|------------|
| Apresentar ao vivo | [`ROTEIRO.md`](ROTEIRO.md) — 10 minutos, com falas e cliques |
| Projetar slides | [`deck.html`](deck.html) — abra no navegador, navegue com ← → |
| Enviar antes da reunião | [`onepager.html`](onepager.html) — imprima como PDF |
| Gravar um vídeo | [`ROTEIRO.md`](ROTEIRO.md) — as marcações **[cena]** são os cortes |
| Entrevista técnica | [`ARQUITETURA.md`](ARQUITETURA.md) — decisões, alternativas e o preço de cada uma |
| Responder "isso faz X?" | [`PERGUNTAS.md`](PERGUNTAS.md) — as 10 perguntas do produto, honestamente |
| Capturar as telas | [`CAPTURAS.md`](CAPTURAS.md) — o que fotografar e em que estado |

## Comandos

```bash
export PROFILE=<seu-profile>
export WAREHOUSE_ID=<id-do-warehouse>

./collect_numbers.sh          # extrai os fatos das tabelas para numbers.json
./collect_numbers.sh --check  # confere se os artefatos ainda batem com a plataforma
./snapshot_demo.sh            # congela o estado atual (rode uma vez, com a demo boa)
./reset_demo.sh               # restaura o estado congelado (~20s)
./reset_demo.sh --dry-run     # valida snapshot e schemas sem alterar nada

./prepare_small_job.sh --measure-only   # mede leve × pesado do job do gatilho
./prepare_small_job.sh                  # forma baseline e primeiro incidente (uma vez)
./trigger_recorrencia.sh                # durante a apresentação: recorrência de verdade (ciclo curto)

./start_demo.sh               # liga warehouse e App e restaura o estado congelado
./stop_demo.sh                # desliga App e warehouse — ligados, consomem cota
./verify_pending.sh           # janela de verificação das features pendentes (retomável)
./verify_pending.sh --reset   # descarta o progresso e começa outra janela

python verify_demo.py           # porta de qualidade do kit
python verify_demo.py --strict  # exige também as capturas de tela
```

## Antes de apresentar

1. `./start_demo.sh` — liga o que a apresentação usa e restaura o estado conhecido.
2. Abra o console e deixe o incidente carregado numa aba.
3. Se for usar o gatilho ao vivo, confirme que `./prepare_small_job.sh` já rodou alguma vez.
4. Leia o bloco 3 do roteiro em voz alta uma vez. É o trecho que sustenta a demo.
5. Ao terminar: `./stop_demo.sh`.

## Cota da Free Edition

O workspace da demo é Databricks Free Edition: estourada a cota, a conta recusa novos runs
(*"Triggering new runs for organization … disabled temporarily"*) e para o App. Para gastar pouco:

- **O job grande (`eict-demo-sales-daily`) não roda mais.** Os números da apresentação vêm do snapshot;
  a verificação e o gatilho usam só o job pequeno.
- **App e warehouse desligados fora de uso** (`stop_demo.sh`).
- **Ciclo por etapas:** o job do ciclo aceita `stages` (ex.: `collect,medallion,correlate,narrate`) e só
  dispara o pipeline Lakeflow quando o collect gravou observação nova (`force_pipeline=true` força).
- **Janela de verificação** (`verify_pending.sh`): 4 runs, ≈ 34 min previstos, orçamento padrão de
  45 min e 8 runs (`BUDGET_MINUTES`, `BUDGET_RUNS`). Confere o bloqueio antes de gastar, para na primeira
  recusa guardando o progresso em `.verify_state.json` (fora do git), sempre desliga App e warehouse, e
  grava `verification_report.md` com o estado de cada uma das 11 features e o consumo previsto × real.
  Tem um passo manual: reconhecer no console o incidente de SLA que a própria janela abre.
  Se o status do App ainda mostrar o bloqueio antigo depois de a cota voltar, use `--skip-precheck` —
  um disparo recusado não gasta compute.
- **Consumo da apresentação** só entra em `numbers.json` medido: `trigger_recorrencia.sh` grava
  `.presentation_cost.json` e `collect_numbers.sh` o transforma no fato `presentation_compute_min`.

## A regra dos números

Todo número citado aqui sai de `numbers.json`, que é gerado por consulta às tabelas.
O `verify_demo.py` reprova qualquer documento que cite um número sem origem — foi assim que
o fator de regressão apareceu como **5.7**, e não como o valor arredondado que circulava de
memória.

## Honestidade da demo

- O estado restaurado é **saída real** de uma execução verdadeira; o `reset_demo.sh` imprime
  a data em que o incidente foi produzido.
- O gatilho ao vivo roda num job menor e abre o incidente **dele**, com 3 evidências em vez de
  4 — não há commit associado. Diga isso na apresentação; está no roteiro.
- O que a plataforma não faz está listado em `PERGUNTAS.md`, pergunta a pergunta.
