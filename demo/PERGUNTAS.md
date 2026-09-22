# As 10 perguntas do produto — onde a demo responde cada uma

O `CONTEXT.md` (§2) lista as perguntas que a EICT promete responder. Esta tabela diz,
sem floreio, quais a demo já responde, onde, e quais ainda não.

| # | Pergunta | Onde a demo responde | Estado |
|---|----------|----------------------|--------|
| 1 | O que está errado ou degradando? | Console → incidentes de runtime **e de qualidade** (contrato violado); `eict_ops.incidents` | ✅ respondida |
| 2 | Por que isso aconteceu? | Console → hipóteses ranqueadas com evidências; `eict_ops.hypotheses` | ✅ respondida |
| 3 | O que mudou desde a última condição saudável? | Console → comparação de runs (commit, ambiente, plano, chave, volume) | ✅ respondida |
| 4 | Qual é o impacto técnico, operacional, financeiro e regulatório? | Console → ativos afetados (lineage), **consumidores declarados no contrato** e custo incremental | ⚠️ parcial: técnico e financeiro sim; regulatório fora do escopo |
| 5 | Quem precisa agir e qual é o SLA? | — | ❌ fora do escopo da demo: ownership e SLA exigem inventário de ativos |
| 6 | Qual ação é recomendada agora? | Roteiro, bloco 3: a evidência aponta o commit a revisar | ⚠️ parcial: diagnóstico sim, recomendação estruturada não |
| 7 | A ação pode ser executada automaticamente ou exige aprovação? | — | ❌ fora do escopo: a demo é somente leitura, sem remediação |
| 8 | Como impedir recorrência? | Console → confirmação humana da causa registra conhecimento | ⚠️ parcial: registra, mas não clusteriza problemas recorrentes |
| 9 | Quais ativos, processos, pessoas e clientes dependem do componente? | Console → descobertos por lineage **e declarados no contrato**, lado a lado; divergência é destacada | ⚠️ parcial: ativos e times donos sim; clientes não |
| 10 | O código e a configuração que causaram a mudança são seguros? | — | ❌ fora do escopo: análise de código e supply chain é fase posterior |

## Como ler esta tabela numa apresentação

Três respondidas por completo, quatro parciais e três fora do escopo. Isso é intencional:
a demo cobre o caminho do diagnóstico — detectar, explicar com evidência, medir impacto —
e deixa explícito o que ainda não faz. Prometer as dez seria o tipo de coisa que a própria
plataforma foi desenhada para não fazer.

## O que a camada de contratos acrescentou

Antes, a pergunta 1 só era respondida para lentidão de job. Agora um contrato declarado por
dataset é avaliado a cada ciclo em sete dimensões — completude, unicidade, validade, freshness,
volume, schema e integridade referencial — e a violação vira incidente pelo mesmo caminho de
evidência e hipótese.

Duas distinções que importam nessa camada:

- **Falha do motor não é dado ruim.** Uma regra que não pôde ser executada vira
  `evaluation_error` e abre um incidente próprio, do tipo `quality_engine_failure`. Confundir
  os dois faria o time investigar dado íntegro.
- **Consumidor declarado e consumidor descoberto são listas diferentes.** Quem está no contrato
  mas não aparece no lineage sugere contrato desatualizado; quem aparece no lineage sem estar no
  contrato sugere uso não governado. Os dois são achados de governança, não ruído.
