"""Discount rules, tier discounts, tax and the pricing engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from shop.orders import Order, OrderLine

TIER_DISCOUNTS = {"standard": 0.0, "silver": 0.02, "gold": 0.05}


class DiscountRule(Protocol):
    def discount_for(self, line: OrderLine) -> float: ...


@dataclass
class CategoryDiscount:
    category: str
    percent: float

    def discount_for(self, line: OrderLine) -> float:
        if line.product.category != self.category:
            return 0.0
        return line.line_total() * self.percent / 100


@dataclass
class BulkDiscount:
    sku: str
    min_quantity: int
    percent: float

    def discount_for(self, line: OrderLine) -> float:
        if line.product.sku != self.sku or line.quantity < self.min_quantity:
            return 0.0
        return line.line_total() * self.percent / 100


@dataclass
class PriceBreakdown:
    subtotal: float
    discount: float
    tax: float
    total: float


class PricingEngine:
    def __init__(self, rules: list[DiscountRule] | None = None, tax_rate: float = 0.2) -> None:
        self.rules = list(rules or [])
        self.tax_rate = tax_rate

    def _line_discount(self, line: OrderLine) -> float:
        return round(max((r.discount_for(line) for r in self.rules), default=0.0), 2)

    def price(self, order: Order) -> PriceBreakdown:
        if order.tier not in TIER_DISCOUNTS:
            raise ValueError(f"unknown tier {order.tier!r}")
        subtotal = round(sum(line.line_total() for line in order.lines), 2)
        line_discounts = sum(self._line_discount(line) for line in order.lines)
        tier_discount = round(TIER_DISCOUNTS[order.tier] * (subtotal - line_discounts), 2)
        discount = round(line_discounts + tier_discount, 2)
        tax = round(self.tax_rate * (subtotal - discount), 2)
        return PriceBreakdown(subtotal, discount, tax, round(subtotal - discount + tax, 2))
