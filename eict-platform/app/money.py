"""Formatação de cifras do showback: nenhum valor aparece sem período, moeda e base de preço."""

from __future__ import annotations

from decimal import Decimal

SIMBOLOS = {"USD": "US$"}
BASES = {"lista": "preço de lista"}


def fmt_money(value: Decimal | float | None, currency: str, period_label: str, price_basis: str = "lista") -> str:
    if value is None:
        return f"não medido · {period_label}"
    simbolo = SIMBOLOS.get(currency, currency)
    return f"{simbolo} {float(value):,.4f} · {period_label} · {BASES.get(price_basis, price_basis)}"


def fmt_share(share: float | None) -> str:
    return "sem base" if share is None else f"{share * 100:.1f}%"
