from shop.invoices import render_csv, render_text
from shop.orders import Order

from conftest import MUG, PEN


def placed(checkout):
    o = Order("A1", "Ada")
    o.add_line(PEN, 10)
    o.add_line(MUG, 1)
    return o, checkout.place_order(o)


def test_text_invoice(checkout):
    o, r = placed(checkout)
    assert render_text(o, r) == "\n".join([
        "Order A1",
        "Pen x10 @ 1.50 = 15.00",
        "Mug x1 @ 8.00 = 8.00",
        "Subtotal: 23.00",
        "Discount: -3.00",
        "Tax: 4.00",
        "Shipping: 5.89",
        "Total: 29.89",
    ])


def test_csv_invoice(checkout):
    o, r = placed(checkout)
    assert render_csv(o, r) == "\n".join([
        "sku,name,quantity,unit_price,line_total",
        "PEN,Pen,10,1.50,15.00",
        "MUG,Mug,1,8.00,8.00",
        ",,,subtotal,23.00",
        ",,,discount,3.00",
        ",,,tax,4.00",
        ",,,shipping,5.89",
        ",,,total,29.89",
    ])
