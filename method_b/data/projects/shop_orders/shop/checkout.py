"""Placing and cancelling orders."""
from __future__ import annotations

from dataclasses import dataclass

from shop.errors import InvalidOrder
from shop.orders import Order
from shop.pricing import PriceBreakdown, PricingEngine
from shop.products import Inventory
from shop.shipping import ShippingCalculator


@dataclass
class Receipt:
    order_id: str
    breakdown: PriceBreakdown
    shipping: float
    grand_total: float


class CheckoutService:
    def __init__(self, inventory: Inventory, pricing: PricingEngine, shipping: ShippingCalculator) -> None:
        self.inventory = inventory
        self.pricing = pricing
        self.shipping = shipping
        self._orders: dict[str, Order] = {}
        self._receipts: dict[str, Receipt] = {}

    def place_order(self, order: Order) -> Receipt:
        if not order.lines or order.status != "open":
            raise InvalidOrder(f"order {order.order_id} cannot be placed")
        self._reserve_all(order)
        breakdown = self.pricing.price(order)
        shipping = self.shipping.cost(order.total_weight(), breakdown.subtotal - breakdown.discount)
        receipt = Receipt(order.order_id, breakdown, shipping, round(breakdown.total + shipping, 2))
        order.status = "placed"
        self._orders[order.order_id] = order
        self._receipts[order.order_id] = receipt
        return receipt

    def _reserve_all(self, order: Order) -> None:
        reserved = []
        try:
            for line in order.lines:
                self.inventory.reserve(line.product.sku, line.quantity)
                reserved.append(line)
        except Exception:
            for line in reserved:
                self.inventory.release(line.product.sku, line.quantity)
            raise

    def cancel(self, order_id: str) -> None:
        order = self._orders.get(order_id)
        if order is None or order.status != "placed":
            raise InvalidOrder(f"order {order_id} cannot be cancelled")
        for line in order.lines:
            self.inventory.release(line.product.sku, line.quantity)
        order.status = "cancelled"

    def get_receipt(self, order_id: str) -> Receipt:
        try:
            return self._receipts[order_id]
        except KeyError:
            raise InvalidOrder(f"no receipt for {order_id}") from None
