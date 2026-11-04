"""Exceptions raised by the shop package."""


class ShopError(Exception):
    """Base class for all shop errors."""


class UnknownProduct(ShopError):
    """No product with this SKU exists."""


class OutOfStock(ShopError):
    """Not enough units in stock."""


class InvalidOrder(ShopError):
    """The order cannot be changed, placed or cancelled in its current state."""
