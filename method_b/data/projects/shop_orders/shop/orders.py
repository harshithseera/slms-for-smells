"""Orders and order lines."""
from __future__ import annotations

from dataclasses import dataclass

from shop.errors import InvalidOrder
from shop.products import Product


@dataclass
class OrderLine:
    product: Product
    quantity: int

    def line_total(self) -> float:
        return round(self.product.unit_price * self.quantity, 2)


class Order:
    def __init__(self, order_id: str, customer: str, tier: str = "standard") -> None:
        self.order_id = order_id
        self.customer = customer
        self.tier = tier
        self.lines: list[OrderLine] = []
        self.status = "open"

    def add_line(self, product: Product, quantity: int) -> None:
        if self.status != "open":
            raise InvalidOrder(f"order {self.order_id} is {self.status}")
        if quantity <= 0:
            raise InvalidOrder("quantity must be positive")
        for line in self.lines:
            if line.product.sku == product.sku:
                line.quantity += quantity
                return
        self.lines.append(OrderLine(product, quantity))

    def total_weight(self) -> float:
        return sum(line.product.weight_kg * line.quantity for line in self.lines)
