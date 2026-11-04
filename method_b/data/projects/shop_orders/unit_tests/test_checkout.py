import pytest

from shop.errors import InvalidOrder, OutOfStock
from shop.orders import Order

from conftest import MUG, NOTEBOOK, PEN


def order_a():
    o = Order("A1", "Ada")
    o.add_line(PEN, 10)
    o.add_line(MUG, 1)
    return o


def test_place_order(checkout, inventory):
    o = order_a()
    r = checkout.place_order(o)
    assert (r.order_id, r.shipping, r.grand_total) == ("A1", 5.89, 29.89)
    assert r.breakdown.total == 24.0
    assert o.status == "placed"
    assert inventory.stock("PEN") == 40 and inventory.stock("MUG") == 19
    assert checkout.get_receipt("A1") == r


def test_free_shipping_and_silver_tier(checkout):
    o = Order("S1", "Sam", tier="silver")
    o.add_line(MUG, 15)
    r = checkout.place_order(o)
    assert (r.breakdown.discount, r.breakdown.tax, r.shipping, r.grand_total) == (2.4, 23.52, 0.0, 141.12)


def test_failed_reservation_is_rolled_back(checkout, inventory):
    o = Order("X", "Xi")
    o.add_line(PEN, 5)
    o.add_line(NOTEBOOK, 11)
    with pytest.raises(OutOfStock):
        checkout.place_order(o)
    assert inventory.stock("PEN") == 50 and inventory.stock("NB") == 10
    assert o.status == "open"


def test_cannot_place_empty_or_twice(checkout):
    with pytest.raises(InvalidOrder):
        checkout.place_order(Order("E", "Em"))
    o = order_a()
    checkout.place_order(o)
    with pytest.raises(InvalidOrder):
        checkout.place_order(o)


def test_cancel(checkout, inventory):
    checkout.place_order(order_a())
    checkout.cancel("A1")
    assert inventory.stock("PEN") == 50 and inventory.stock("MUG") == 20
    with pytest.raises(InvalidOrder):
        checkout.cancel("A1")
    with pytest.raises(InvalidOrder):
        checkout.cancel("nope")
    with pytest.raises(InvalidOrder):
        checkout.get_receipt("nope")
