import pytest

from shop.orders import Order, OrderLine
from shop.pricing import BulkDiscount, CategoryDiscount, PriceBreakdown, PricingEngine
from shop.shipping import ShippingCalculator

from conftest import MUG, NOTEBOOK, PEN


def test_rules():
    assert CategoryDiscount("stationery", 10).discount_for(OrderLine(PEN, 10)) == pytest.approx(1.5)
    assert CategoryDiscount("stationery", 10).discount_for(OrderLine(MUG, 1)) == 0
    assert BulkDiscount("PEN", 10, 20).discount_for(OrderLine(PEN, 9)) == 0
    assert BulkDiscount("PEN", 10, 20).discount_for(OrderLine(PEN, 10)) == pytest.approx(3.0)


def test_best_rule_per_line_no_stacking(pricing):
    o = Order("a", "Ada")
    o.add_line(PEN, 10)
    o.add_line(MUG, 1)
    assert pricing.price(o) == PriceBreakdown(subtotal=23.0, discount=3.0, tax=4.0, total=24.0)


def test_tier_discount_after_rule_discounts(pricing):
    o = Order("b", "Bob", tier="gold")
    o.add_line(NOTEBOOK, 2)
    assert pricing.price(o) == PriceBreakdown(subtotal=8.0, discount=1.16, tax=1.37, total=8.21)


def test_unknown_tier():
    o = Order("c", "Cy", tier="platinum")
    o.add_line(MUG, 1)
    with pytest.raises(ValueError):
        PricingEngine().price(o)


def test_no_rules_custom_tax():
    o = Order("d", "Di")
    o.add_line(MUG, 2)
    assert PricingEngine(tax_rate=0.1).price(o) == PriceBreakdown(16.0, 0.0, 1.6, 17.6)


def test_shipping():
    s = ShippingCalculator()
    assert s.cost(0.6, 20.0) == 5.89
    assert s.cost(10.0, 100.0) == 0.0
    assert ShippingCalculator(base_fee=2.0, per_kg=1.0, free_over=50.0).cost(1.5, 49.99) == 3.5
