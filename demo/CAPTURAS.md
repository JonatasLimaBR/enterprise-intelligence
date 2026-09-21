# Capturas de tela — o que fotografar e em que estado

O console exige login, então estas capturas são feitas por você. Cada item diz o
**arquivo** de destino, a **tela** e o **estado** exigido. Depois de capturar, rode
`python verify_demo.py` — ele acusa qualquer imagem referenciada que ainda falte.

Antes de começar: `PROFILE=<seu-profile> ./reset_demo.sh` para garantir o estado congelado.

---

## Obrigatórias (contam a história)

### 1. `img/01-lista-incidentes.png`
- **Tela:** console → página inicial, barra lateral visível
- **Estado:** um incidente na lista, estado `detected`
- **Precisa aparecer:** o job, o estado e a data de detecção
- **Usada em:** README, deck (bloco 2), roteiro

### 2. `img/02-rca-evidencias.png`
- **Tela:** console → incidente → seção de hipóteses
- **Estado:** hipótese #1 expandida, com as quatro evidências visíveis
- **Precisa aparecer:** a confiança, e as evidências de skew, plano, commit e volume
- **Usada em:** README, deck (bloco 3) — **é a captura mais importante do kit**

### 3. `img/03-impacto-custo.png`
- **Tela:** console → incidente → cabeçalho e seção de impacto
- **Estado:** cartões do topo carregados e lista de ativos afetados visível
- **Precisa aparecer:** o custo incremental e os três ativos
- **Usada em:** README, deck (bloco 5)

---

## Complementares (enriquecem, não bloqueiam)

### 4. `img/04-diff-runs.png`
- **Tela:** console → incidente → comparação de runs
- **Estado:** tabela completa, com spill e GC marcados como indisponíveis
- **Precisa aparecer:** a linha do commit mudando e a linha do ambiente igual

### 5. `img/05-hipoteses-alternativas.png`
- **Tela:** console → incidente → hipóteses #2 e #3 expandidas
- **Estado:** evidências **contra** visíveis nas duas
- **Precisa aparecer:** a confiança baixa e o texto da evidência que derruba cada uma

### 6. `img/06-narrativa-fallback.png`
- **Tela:** console → incidente → resumo
- **Estado:** rodapé mostrando origem determinística e o motivo da rejeição
- **Precisa aparecer:** os identificadores de evidência citados nas frases

### 7. `img/07-timeline.png`
- **Tela:** console → incidente → linha do tempo
- **Estado:** as entradas de detecção e recorrência

### 8. `img/08-dashboard-comercial.png`
- **Tela:** dashboard AI/BI "Comercial"
- **Estado:** gráficos carregados
- **Por quê:** é o ativo de negócio que aparece como impactado

### 9. `img/09-pipeline-lakeflow.png`
- **Tela:** pipeline Lakeflow → grafo das tabelas
- **Estado:** última execução bem-sucedida
- **Por quê:** mostra o caminho bronze → silver → gold para a audiência técnica

### 10. `img/10-job-ciclo.png`
- **Tela:** job `eict-cycle` → visão das tarefas
- **Estado:** execução concluída, com as cinco tarefas verdes
- **Por quê:** mostra a orquestração de ponta a ponta

---

## Dicas de captura

- Largura de 1440 px dá boa leitura no deck sem virar arquivo gigante.
- Use tema claro: o deck tem fundo escuro e o contraste ajuda.
- Corte a barra do navegador; ela mostra a URL do workspace, que não deve ir ao repositório.
- Se alguma tela mostrar seu e-mail, borre antes de salvar — o verificador não lê imagens.
