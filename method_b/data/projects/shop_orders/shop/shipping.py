"""Shipping cost."""
from __future__ import annotations


class ShippingCalculator:
    def __init__(self, base_fee: float = 4.99, per_kg: float = 1.5, free_over: float = 100.0) -> None:
        self.base_fee = base_fee
        self.per_kg = per_kg
        self.free_over = free_over

    def cost(self, weight_kg: float, amount: float) -> float:
        if amount >= self.free_over:
            return 0.0
        return round(self.base_fee + self.per_kg * weight_kg, 2)
