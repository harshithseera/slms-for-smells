import pytest

from shop.errors import InvalidOrder
from shop.orders import Order, OrderLine

from conftest import MUG, PEN


def test_new_order_defaults():
    o = Order("o1", "Ada")
    assert (o.order_id, o.customer, o.tier, o.lines, o.status) == ("o1", "Ada", "standard", [], "open")


def test_add_line_merges_same_product():
    o = Order("o1", "Ada")
    o.add_line(PEN, 2)
    o.add_line(MUG, 1)
    o.add_line(PEN, 3)
    assert [(l.product.sku, l.quantity) for l in o.lines] == [("PEN", 5), ("MUG", 1)]
    assert o.total_weight() == pytest.approx(0.5)


def test_add_line_rejects_bad_quantity_and_closed_orders():
    o = Order("o1", "Ada")
    with pytest.raises(InvalidOrder):
        o.add_line(PEN, 0)
    o.status = "placed"
    with pytest.raises(InvalidOrder):
        o.add_line(PEN, 1)


def test_line_total_rounded():
    assert OrderLine(PEN, 3).line_total() == 4.5
