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
./trigger_recorrencia.sh                # durante a apresentação: recorrência de verdade

python verify_demo.py           # porta de qualidade do kit
python verify_demo.py --strict  # exige também as capturas de tela
```

## Antes de apresentar

1. `./reset_demo.sh` — garante o estado conhecido.
2. Abra o console e deixe o incidente carregado numa aba.
3. Se for usar o gatilho ao vivo, confirme que `./prepare_small_job.sh` já rodou alguma vez.
4. Leia o bloco 3 do roteiro em voz alta uma vez. É o trecho que sustenta a demo.

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
