import pytest

from shop.checkout import CheckoutService
from shop.pricing import BulkDiscount, CategoryDiscount, PricingEngine
from shop.products import Inventory, Product
from shop.shipping import ShippingCalculator

PEN = Product("PEN", "Pen", 1.50, "stationery", 0.02)
NOTEBOOK = Product("NB", "Notebook", 4.00, "stationery", 0.3)
MUG = Product("MUG", "Mug", 8.00, "kitchen", 0.4)
RULES = [CategoryDiscount("stationery", 10), BulkDiscount("PEN", 10, 20)]


@pytest.fixture
def inventory():
    inv = Inventory()
    inv.add_product(PEN, stock=50)
    inv.add_product(NOTEBOOK, stock=10)
    inv.add_product(MUG, stock=20)
    return inv


@pytest.fixture
def pricing():
    return PricingEngine(RULES)


@pytest.fixture
def checkout(inventory, pricing):
    return CheckoutService(inventory, pricing, ShippingCalculator())
