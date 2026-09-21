# Roteiro da demo — 10 minutos

> Fonte dos números: `demo/numbers.json`, gerado por `collect_numbers.sh` direto das tabelas.
> Antes de começar: `PROFILE=<seu-profile> ./reset_demo.sh` e abra o console.
> Legenda: **[cena]** marca o corte para gravação · **[clique]** marca a ação na tela.

---

## 1. O problema

**[cena: tela do job no Databricks]**

Este job de vendas rodava em pouco menos de três minutos. Passou a levar vinte e seis.

O Spark UI mostra isso. Mostra o tempo, mostra os estágios, mostra que uma tarefa demorou muito mais que as outras. O que ele não responde é o que interessa: por que mudou, o que mudou, quem é afetado e quanto custa.

Essa pergunta hoje é respondida por uma pessoa abrindo cinco abas — Spark UI, histórico de execuções, Git, catálogo e faturamento — e cruzando tudo de cabeça. Leva de trinta minutos a algumas horas, e o resultado depende de quem está de plantão.

É esse trabalho que a plataforma faz.

---

## 2. O incidente

**[cena: console da EICT, lista de incidentes]**

**[clique: abrir o incidente do topo]**

Duas execuções lentas geraram **um** incidente, não dois. A chave de correlação é o job mais o tipo de problema, então repetição vira nova entrada na linha do tempo, não um alerta novo. Essa é a diferença entre monitoramento e operação: o operador vê um problema, não uma enxurrada.

**[clique opcional, ao vivo: rodar `./trigger_recorrencia.sh` num segundo terminal]**

Enquanto conversamos, acabei de disparar uma execução lenta num job menor. Em poucos minutos ela aparece aqui como recorrência — no incidente daquele job, não neste. Vale dizer: naquele incidente a hipótese terá três evidências, porque não há commit associado; a história completa é a deste aqui.

---

## 3. O RCA

**[cena: seção de hipóteses, hipótese #1 expandida]**

A hipótese no topo diz: skew na chave do join introduzido por mudança de código. Ela está em **0.9** de confiança, sustentada por quatro evidências. Vou ler as quatro, porque o valor está nelas, não no número.

**Primeira, os dados.** Um único cliente concentra **40** por cento das linhas — são **24** milhões de um total de **60** milhões. Esse desequilíbrio sempre existiu.

**Segunda, o plano de execução.** No run lento aparece um operador `Window` que não existia no run saudável. O Spark não divide partições de janela; a chave quente virou uma tarefa gigante.

**Terceira, a mudança.** O commit que introduziu essa janela está identificado, com o arquivo que alterou.

**Quarta, e a mais importante: o volume de entrada não mudou.** A mesma quantidade de linhas, antes e depois. Isso **descarta** a explicação mais comum — "os dados cresceram" — e é o que transforma correlação em diagnóstico.

---

## 4. Por que isso não é chute

**[cena: hipóteses alternativas]**

**[clique: expandir as duas hipóteses seguintes]**

As alternativas continuam listadas, em **0.05**, e cada uma traz a evidência que a derruba: o ambiente de execução é idêntico ao do run saudável, e o volume é o mesmo. Uma ferramenta que só mostra a resposta certa não dá para auditar; esta mostra o que considerou e por que descartou.

Repare no teto. Nenhuma hipótese passa de **0.9** — esse é o limite de inferência sem confirmação humana, e está no código, não numa recomendação. Quando alguém clica em "confirmar causa", aí sim o registro passa a ter dono e virar conhecimento.

---

## 5. Impacto e custo

**[cena: seção de impacto]**

O incidente aponta **3** ativos afetados: a tabela de saída, o job e o painel de vendas que consome essa tabela. Isso vem do lineage do catálogo, não de uma configuração manual.

**[clique: cartão de custo]**

E o custo incremental desta execução: **0.0682** dólares. Parece pouco, e é — porque é uma demonstração. O ponto é o mecanismo: o valor vem da tabela de faturamento, e enquanto ela não chega, o campo aparece como indisponível, nunca estimado.

---

## 6. O guardrail

**[cena: resumo do incidente]**

Por último, o texto que você leu no topo. Ele foi escrito por regra, não pelo modelo de linguagem.

O modelo até respondeu, mas a resposta foi **rejeitada** na validação, porque não respeitou o formato exigido — cada frase precisa citar o identificador de uma evidência que exista. Sem isso, a plataforma descarta e escreve o texto determinístico.

Esse é o princípio que sustenta o resto: evidência antes de inferência. A IA redige; quem decide o que é verdade são as regras e a pessoa.

**[cena final]**

O código está aberto, com **100** testes e **96** por cento de cobertura no núcleo de domínio. E, honestamente, **8** dos problemas mais interessantes só apareceram rodando de verdade — nenhum teste local os teria pego.
