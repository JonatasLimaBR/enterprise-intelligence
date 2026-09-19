# CI/CD e Secure SDLC

## Pipeline

1. lint/format/type check;
2. unit/property tests;
3. secret scan;
4. SAST/SCA/license;
5. schema/API compatibility;
6. build reproducível;
7. SBOM e assinatura;
8. container/IaC scan;
9. integration/evaluation;
10. policy gate;
11. deploy canary;
12. post-deploy verification;
13. promotion ou rollback.

## Provenance

Gerar attestations de source, builder, dependencies e artifact digest. Registrar assistência de IA quando ferramenta/política suportar. Não armazenar prompt sensível sem necessidade.

## Environments

Promover o mesmo artefato imutável. Configuração externa e versionada. Aprovações proporcionais ao Change Risk Score.

## Database/event migrations

Expand-migrate-contract; consumers toleram versões N/N-1; replay tests antes de remover campos.

