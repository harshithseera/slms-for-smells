"""Products and stock levels."""
from __future__ import annotations

from dataclasses import dataclass

from shop.errors import OutOfStock, ShopError, UnknownProduct


@dataclass
class Product:
    sku: str
    name: str
    unit_price: float
    category: str
    weight_kg: float


class Inventory:
    def __init__(self) -> None:
        self._products: dict[str, Product] = {}
        self._stock: dict[str, int] = {}

    def add_product(self, product: Product, stock: int = 0) -> None:
        if product.sku in self._products:
            raise ShopError(f"duplicate SKU {product.sku}")
        self._products[product.sku] = product
        self._stock[product.sku] = stock

    def get(self, sku: str) -> Product:
        try:
            return self._products[sku]
        except KeyError:
            raise UnknownProduct(sku) from None

    def stock(self, sku: str) -> int:
        self.get(sku)
        return self._stock[sku]

    def restock(self, sku: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        self._stock[sku] = self.stock(sku) + quantity

    def reserve(self, sku: str, quantity: int) -> None:
        if quantity > self.stock(sku):
            raise OutOfStock(f"{sku}: {quantity} requested, {self._stock[sku]} in stock")
        self._stock[sku] -= quantity

    def release(self, sku: str, quantity: int) -> None:
        self._stock[sku] = self.stock(sku) + quantity
