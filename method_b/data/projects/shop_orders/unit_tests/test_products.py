import pytest

from shop.errors import OutOfStock, ShopError, UnknownProduct
from shop.products import Inventory

from conftest import PEN


def test_stock_operations(inventory):
    inventory.restock("PEN", 5)
    inventory.reserve("PEN", 15)
    assert inventory.stock("PEN") == 40
    inventory.release("PEN", 3)
    assert inventory.stock("PEN") == 43
    assert inventory.get("PEN") is PEN


def test_errors(inventory):
    with pytest.raises(ShopError):
        inventory.add_product(PEN)
    with pytest.raises(UnknownProduct):
        inventory.stock("NOPE")
    with pytest.raises(ValueError):
        inventory.restock("PEN", 0)
    with pytest.raises(OutOfStock):
        inventory.reserve("MUG", 21)
    assert inventory.stock("MUG") == 20


def test_default_stock_is_zero():
    inv = Inventory()
    inv.add_product(PEN)
    assert inv.stock("PEN") == 0
