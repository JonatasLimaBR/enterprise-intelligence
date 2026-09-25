"""Alocação de custo: de quem é cada centavo do billing, com precedência determinística.

Cada linha de uso recebe exatamente uma alocação, na ordem: conflito → regra de domínio →
contrato → pool da plataforma → não alocado. O que não tem dono fica visível com o nome do
recurso; nada some. Dinheiro é `Decimal` do começo ao fim: a soma das categorias é igual à
soma da entrada por construção, não por tolerância.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from eict.domain.producers import normalize

DOMINIO = "dominio"
PLATAFORMA = "plataforma"
NAO_ALOCADO = "nao_alocado"

JOB = "job"
PIPELINE = "pipeline"
WAREHOUSE = "warehouse"
APP = "app"

REGRA_ATIVA = "ativa"
REGRA_CONFLITO = "conflito"
ARQUIVO_RECUSADO = "arquivo_recusado"

PRICE_BASIS = "lista"
TOLERANCE_RATIO = Decimal("0.005")
TOLERANCE_FLOOR = Decimal("1")
ZERO = Decimal("0")


class AllocationError(ValueError):
    """Arquivo de alocação inválido: recusado inteiro, os demais seguem."""


@dataclass(frozen=True)
class Product:
    product: str
    owner: str
    jobs: tuple[str, ...]


@dataclass(frozen=True)
class DomainFile:
    business_unit: str
    domain: str
    owner: str
    products: tuple[Product, ...]
    source_file: str = ""


@dataclass(frozen=True)
class PlatformPool:
    pool: str
    owner: str
    jobs: tuple[str, ...]
    apps: tuple[str, ...]
    source_file: str = ""


@dataclass(frozen=True)
class ContractOwner:
    contract_id: str
    owner: str
    asset: str


@dataclass(frozen=True)
class UsageLine:
    resource_kind: str
    resource_id: str
    resource_name: str
    run_id: str
    origin_product: str
    dbus: Decimal
    cost: Decimal


@dataclass(frozen=True)
class Allocation:
    line: UsageLine
    category: str
    reason: str
    business_unit: str = ""
    domain: str = ""
    product: str = ""
    owner: str = ""


@dataclass(frozen=True)
class Target:
    business_unit: str
    domain: str
    product: str
    owner: str
    source_file: str


@dataclass(frozen=True)
class RuleSet:
    targets: dict[str, Target]
    conflicts: dict[str, tuple[str, ...]]
    contract_owners: dict[str, tuple[ContractOwner, ...]]
    platform: PlatformPool | None
    platform_pipeline_id: str = ""
    platform_warehouse_id: str = ""

    def classify(self, line: UsageLine) -> Allocation:
        if line.resource_kind == JOB:
            return self._classify_job(line)
        if self._is_platform(line):
            return self._platform(line)
        if line.resource_kind in (PIPELINE, WAREHOUSE, APP) and line.resource_id:
            nome = line.resource_name or line.resource_id
            return Allocation(line, NAO_ALOCADO, f"sem regra: {line.resource_kind} {nome}")
        return Allocation(line, NAO_ALOCADO, f"recurso não identificado ({line.origin_product or 'sem produto'})")

    def _classify_job(self, line: UsageLine) -> Allocation:
        chave = normalize(line.resource_name)
        if chave in self.conflicts:
            return Allocation(line, NAO_ALOCADO, f"conflito entre {' e '.join(self.conflicts[chave])}")
        alvo = self.targets.get(chave)
        if alvo is not None:
            return Allocation(
                line, DOMINIO, f"regra de alocação ({alvo.source_file})",
                alvo.business_unit, alvo.domain, alvo.product, alvo.owner,
            )
        contratos = self.contract_owners.get(chave)
        if contratos:
            primeiro, *outros = contratos
            motivo = "contrato"
            if outros:
                motivo += f" ({primeiro.contract_id}; também produz {', '.join(item.contract_id for item in outros)})"
            return Allocation(line, DOMINIO, motivo, "", primeiro.contract_id, primeiro.asset, primeiro.owner)
        if self._is_platform(line):
            return self._platform(line)
        if not chave:
            return Allocation(line, NAO_ALOCADO, f"sem regra: job {line.resource_id} sem nome")
        return Allocation(line, NAO_ALOCADO, f"sem regra: {line.resource_name}")

    def _is_platform(self, line: UsageLine) -> bool:
        if line.resource_kind == PIPELINE:
            return bool(self.platform_pipeline_id) and line.resource_id == self.platform_pipeline_id
        if line.resource_kind == WAREHOUSE:
            return bool(self.platform_warehouse_id) and line.resource_id == self.platform_warehouse_id
        if self.platform is None:
            return False
        if line.resource_kind == JOB:
            return normalize(line.resource_name) in {normalize(item) for item in self.platform.jobs}
        if line.resource_kind == APP:
            return normalize(line.resource_name) in {normalize(item) for item in self.platform.apps}
        return False

    def _platform(self, line: UsageLine) -> Allocation:
        pool = self.platform.pool if self.platform else "plataforma-eict"
        dono = self.platform.owner if self.platform else ""
        return Allocation(line, PLATAFORMA, "pool da plataforma", "", pool, "", dono)


def _text(payload: dict, campo: str) -> str:
    return str(payload.get(campo) or "").strip()


def _names(valor: object, source: str, campo: str) -> tuple[str, ...]:
    if valor is None:
        return ()
    if not isinstance(valor, list):
        raise AllocationError(f"{source}: `{campo}` precisa ser uma lista")
    return tuple(str(item).strip() for item in valor if str(item).strip())


def parse_domain(payload: object, source: str = "") -> DomainFile:
    if not isinstance(payload, dict):
        raise AllocationError(f"{source}: conteúdo não é um mapeamento")
    faltando = [campo for campo in ("business_unit", "domain", "owner") if not _text(payload, campo)]
    if faltando:
        raise AllocationError(f"{source}: campos obrigatórios ausentes: {', '.join(faltando)}")
    produtos_brutos = payload.get("products")
    if not isinstance(produtos_brutos, list) or not produtos_brutos:
        raise AllocationError(f"{source}: `products` precisa de ao menos um produto")
    produtos: list[Product] = []
    vistos: set[str] = set()
    for indice, bruto in enumerate(produtos_brutos, start=1):
        if not isinstance(bruto, dict) or not _text(bruto, "product"):
            raise AllocationError(f"{source}: produto nº {indice} sem `product`")
        jobs = _names(bruto.get("jobs"), source, "jobs")
        if not jobs:
            raise AllocationError(f"{source}: produto {bruto['product']} sem `jobs`")
        for job in jobs:
            chave = normalize(job)
            if chave in vistos:
                raise AllocationError(f"{source}: job {job} listado mais de uma vez no arquivo")
            vistos.add(chave)
        produtos.append(Product(_text(bruto, "product"), _text(bruto, "owner") or _text(payload, "owner"), jobs))
    return DomainFile(
        business_unit=_text(payload, "business_unit"),
        domain=_text(payload, "domain"),
        owner=_text(payload, "owner"),
        products=tuple(produtos),
        source_file=source,
    )


def parse_platform(payload: object, source: str = "") -> PlatformPool:
    if not isinstance(payload, dict):
        raise AllocationError(f"{source}: conteúdo não é um mapeamento")
    faltando = [campo for campo in ("pool", "owner") if not _text(payload, campo)]
    if faltando:
        raise AllocationError(f"{source}: campos obrigatórios ausentes: {', '.join(faltando)}")
    return PlatformPool(
        pool=_text(payload, "pool"),
        owner=_text(payload, "owner"),
        jobs=_names(payload.get("jobs"), source, "jobs"),
        apps=_names(payload.get("apps"), source, "apps"),
        source_file=source,
    )


def build_rules(
    domains: list[DomainFile] | tuple[DomainFile, ...],
    platform: PlatformPool | None,
    contracts: list[tuple[str, ContractOwner]] | tuple[tuple[str, ContractOwner], ...] = (),
    platform_pipeline_id: str = "",
    platform_warehouse_id: str = "",
) -> RuleSet:
    """Regras prontas para classificar. `contracts` = pares (produtor, contrato)."""
    donos_por_job: dict[str, list[str]] = {}
    alvos: dict[str, Target] = {}
    for arquivo in domains:
        for produto in arquivo.products:
            for job in produto.jobs:
                chave = normalize(job)
                donos_por_job.setdefault(chave, []).append(arquivo.source_file)
                alvos[chave] = Target(
                    arquivo.business_unit, arquivo.domain, produto.product, produto.owner, arquivo.source_file
                )
    conflitos = {chave: tuple(sorted(set(arquivos))) for chave, arquivos in donos_por_job.items() if len(arquivos) > 1}
    for chave in conflitos:
        alvos.pop(chave, None)
    por_produtor: dict[str, list[ContractOwner]] = {}
    for produtor, contrato in contracts:
        chave = normalize(produtor)
        if chave:
            por_produtor.setdefault(chave, []).append(contrato)
    return RuleSet(
        targets=alvos,
        conflicts=conflitos,
        contract_owners={
            chave: tuple(sorted(itens, key=lambda item: item.contract_id)) for chave, itens in por_produtor.items()
        },
        platform=platform,
        platform_pipeline_id=platform_pipeline_id,
        platform_warehouse_id=platform_warehouse_id,
    )


def allocate(lines: list[UsageLine], rules: RuleSet) -> list[Allocation]:
    """Uma alocação por linha, nunca zero, nunca duas."""
    return [rules.classify(line) for line in lines]


def rule_rows(
    domains: list[DomainFile] | tuple[DomainFile, ...],
    platform: PlatformPool | None,
    rules: RuleSet,
    errors: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    loaded_at: datetime,
) -> list[dict]:
    """O catálogo carregado, com o estado de cada regra e os arquivos recusados."""
    linhas = []
    for arquivo in domains:
        for produto in arquivo.products:
            for job in produto.jobs:
                conflito = rules.conflicts.get(normalize(job))
                linhas.append(
                    {
                        "source_file": arquivo.source_file,
                        "kind": "dominio",
                        "business_unit": arquivo.business_unit,
                        "domain": arquivo.domain,
                        "product": produto.product,
                        "job_name": job,
                        "owner": produto.owner,
                        "status": REGRA_CONFLITO if conflito else REGRA_ATIVA,
                        "detail": f"também em {', '.join(item for item in conflito if item != arquivo.source_file)}"
                        if conflito
                        else "",
                        "loaded_at": loaded_at,
                    }
                )
    if platform is not None:
        for nome in (*platform.jobs, *platform.apps):
            linhas.append(
                {
                    "source_file": platform.source_file,
                    "kind": "plataforma",
                    "business_unit": "",
                    "domain": platform.pool,
                    "product": "",
                    "job_name": nome,
                    "owner": platform.owner,
                    "status": REGRA_ATIVA,
                    "detail": "",
                    "loaded_at": loaded_at,
                }
            )
    for arquivo, erro in errors:
        linhas.append(
            {
                "source_file": arquivo,
                "kind": "",
                "business_unit": "",
                "domain": "",
                "product": "",
                "job_name": "",
                "owner": "",
                "status": ARQUIVO_RECUSADO,
                "detail": erro,
                "loaded_at": loaded_at,
            }
        )
    return linhas


@dataclass(frozen=True)
class Totals:
    allocated: Decimal = ZERO
    platform_pool: Decimal = ZERO
    unallocated: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return self.allocated + self.platform_pool + self.unallocated

    @property
    def allocated_share(self) -> float | None:
        """Fração com dono entre o que deveria ter dono; o pool fica fora do denominador."""
        base = self.allocated + self.unallocated
        return float(self.allocated / base) if base else None


def totals(allocations: list[Allocation]) -> Totals:
    por_categoria = {DOMINIO: ZERO, PLATAFORMA: ZERO, NAO_ALOCADO: ZERO}
    for item in allocations:
        por_categoria[item.category] += item.line.cost
    return Totals(por_categoria[DOMINIO], por_categoria[PLATAFORMA], por_categoria[NAO_ALOCADO])


@dataclass(frozen=True)
class Reconciliation:
    total_billing: Decimal
    totals: Totals
    difference: Decimal
    tolerance: Decimal
    reconciled: bool
    reason: str = ""
    currencies: tuple[str, ...] = field(default_factory=tuple)


def tolerance(total: Decimal) -> Decimal:
    return max(abs(total) * TOLERANCE_RATIO, TOLERANCE_FLOOR)


def reconcile(total_billing: Decimal, allocated: Totals, currencies: tuple[str, ...] = ("USD",)) -> Reconciliation:
    diferenca = abs(total_billing - allocated.total)
    limite = tolerance(total_billing)
    moedas = tuple(sorted({item for item in currencies if item}))
    if len(moedas) > 1:
        return Reconciliation(
            total_billing, allocated, diferenca, limite, False,
            f"mais de uma moeda no período: {', '.join(moedas)}", moedas,
        )
    if diferenca > limite:
        return Reconciliation(
            total_billing, allocated, diferenca, limite, False,
            f"diferença de {diferenca:.4f} acima da tolerância de {limite:.4f}", moedas,
        )
    return Reconciliation(total_billing, allocated, diferenca, limite, True, "", moedas)


def allocation_rows(allocations: list[Allocation]) -> list[dict]:
    """Uma linha por recurso e destino — o grão de run fica só para as unidades."""
    grupos: dict[tuple, dict] = {}
    for item in allocations:
        linha = item.line
        chave = (
            item.category, item.business_unit, item.domain, item.product, item.owner,
            linha.resource_kind, linha.resource_id, linha.resource_name, item.reason,
        )
        grupo = grupos.setdefault(
            chave,
            {
                "category": item.category,
                "business_unit": item.business_unit,
                "domain": item.domain,
                "product": item.product,
                "owner": item.owner,
                "resource_kind": linha.resource_kind,
                "resource_id": linha.resource_id,
                "resource_name": linha.resource_name,
                "reason": item.reason,
                "dbus": ZERO,
                "cost": ZERO,
            },
        )
        grupo["dbus"] += linha.dbus
        grupo["cost"] += linha.cost
    return sorted(grupos.values(), key=lambda row: (row["category"], -row["cost"], row["resource_name"]))


@dataclass(frozen=True)
class Period:
    label: str
    start: datetime
    end: datetime
    current: bool

    @property
    def status_label(self) -> str:
        if self.current:
            return "mês corrente"
        return "fechado — sujeito a reprocessamento do billing"


def periods(now: datetime) -> tuple[Period, Period]:
    """Mês anterior e mês corrente, em UTC — o fuso de `usage_date` no billing."""
    inicio_corrente = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if inicio_corrente.month == 1:
        inicio_anterior = inicio_corrente.replace(year=inicio_corrente.year - 1, month=12)
    else:
        inicio_anterior = inicio_corrente.replace(month=inicio_corrente.month - 1)
    return (
        Period(inicio_anterior.strftime("%Y-%m"), inicio_anterior, inicio_corrente, False),
        Period(inicio_corrente.strftime("%Y-%m"), inicio_corrente, now, True),
    )
