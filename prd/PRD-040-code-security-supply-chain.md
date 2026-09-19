# PRD-040 — Code, Security e Supply Chain Intelligence

## Objetivo

Avaliar o risco real de mudanças e software, combinando qualidade de código, evidências de segurança, proveniência, dependências, criticidade e blast radius.

## Fontes

Git providers, CI/CD, scanners SAST/SCA/secrets/IaC/container/license, SBOM, artifact registry, deployment platform, cloud posture, SIEM e catálogo.

## Code Health

Dimensões configuráveis:

- maintainability;
- reliability;
- security;
- tests;
- performance;
- data engineering practices;
- documentation;
- operability.

## Achados específicos de Data/AI

- UDFs que impedem otimização nativa;
- collect/toPandas indevidos;
- repartition/coalesce sem justificativa;
- joins e cartesian products perigosos;
- leitura sem pruning;
- schema inference em produção;
- ausência de checkpoints/expectations;
- vazamento entre treino e teste;
- prompt ou ferramenta sem versionamento;
- logging de PII;
- credenciais em notebook;
- modelos/pacotes não fixados.

## Proveniência de código

### Estados canônicos

1. Human-authored verified.
2. AI-assisted declared/verified.
3. AI-generated verified.
4. Mixed verified.
5. Unknown.

### Evidências aceitáveis

Attestation assinada do IDE/agente, metadata de commit/PR, declaração do autor, logs corporativos autorizados e artefatos de geração. Detecção estilométrica pode apenas gerar sinal não conclusivo.

### Proibições

- decisão trabalhista ou disciplinar baseada em AI-likeness;
- exposição pública de ranking de pessoas;
- coleta de conteúdo do IDE fora da política;
- equiparar uso de IA a baixa qualidade.

## Change Risk Score

Entradas: criticidade, blast radius, tamanho/complexidade da mudança, segurança, cobertura, provenance, schema/data contract, dependências, histórico, rollback, observabilidade, ambiente e janela.

Saídas:

- score 0–100;
- faixa e explicação;
- fatores dominantes;
- evidências;
- gates exigidos;
- plano mínimo de validação;
- override governado.

## Supply Chain

Construir SBOM relacional e ligar pacote/CVE a artefato, deployment, aplicação, dataset, agente e processo. Priorizar por exploitability, reachability, exposição, privilégio e criticidade — não apenas CVSS.

## Gates de PR/deploy

- secrets críticos: bloqueio obrigatório;
- vulnerabilidade crítica explorável: bloqueio ou exceção CISO;
- contrato incompatível: aprovação de produtores/consumidores;
- cobertura abaixo da policy: justificativa ou bloqueio;
- mudança de alto risco: two-person approval, canary e rollback testado;
- AI-generated verified: verificações adicionais conforme política, sem presunção de defeito.

## Aceite

- findings deduplicados entre scanners;
- cada finding preserva fonte e fingerprint;
- score reproduzível para mesma versão de policy;
- overrides expiram e têm owner;
- correlação deployment-incidente mensurável;
- nenhum segredo é copiado para o data lake de observabilidade.

## KPIs

Change failure rate, escaped defects, MTTR por change, mean time to remediate, vulnerable asset exposure, secret leakage, coverage delta, false positive rate e policy override aging.

