# Estratégia de Testes

## Pirâmide

- unitários: domínio, scoring, redaction, policy inputs;
- property-based: idempotência, invariantes, serialização;
- contract: fontes e APIs;
- integração: stores, queue e graph;
- end-to-end: incident lifecycle;
- chaos/resilience: atraso, duplicação, outage e throttling;
- security: SAST, DAST, SCA, secrets, IaC e abuse cases;
- AI evaluation: datasets, tools, factuality e safety.

## Cenários dourados MVP

1. skew após novo join;
2. pipeline atrasado por SAP upstream;
3. cluster memory-bound, CPU normal;
4. custo elevado sem crescimento de volume;
5. job verde com freshness inválida;
6. alteração incompatível de schema;
7. commit sem relação causal;
8. múltiplos alertas do mesmo incidente;
9. integração ITSM indisponível;
10. tool request proibida por policy.

## Critérios de qualidade IA

- toda afirmação material aponta evidência;
- nenhum secret/PII vazado;
- hipóteses rotuladas;
- action suggestions dentro do allowlist;
- prompt injection não altera política;
- fallback funciona sem provider.

## Performance

Load tests para event throughput, incident query, graph traversal e fan-out. Testar noisy tenant, cardinalidade extrema, replay e hot partitions.

## Release gates

Sem vulnerabilidade crítica aberta, contract compatibility, score regression dentro do limite, SLO smoke tests e rollback validado.

