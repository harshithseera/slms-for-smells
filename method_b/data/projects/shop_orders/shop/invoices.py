"""Text and CSV invoices."""
from __future__ import annotations

from shop.checkout import Receipt
from shop.orders import Order


def _summary(receipt: Receipt) -> list[tuple[str, float]]:
    b = receipt.breakdown
    return [("subtotal", b.subtotal), ("discount", b.discount), ("tax", b.tax),
            ("shipping", receipt.shipping), ("total", receipt.grand_total)]


def render_text(order: Order, receipt: Receipt) -> str:
    out = [f"Order {order.order_id}"]
    for line in order.lines:
        p = line.product
        out.append(f"{p.name} x{line.quantity} @ {p.unit_price:.2f} = {line.line_total():.2f}")
    for label, value in _summary(receipt):
        sign = "-" if label == "discount" else ""
        out.append(f"{label.capitalize()}: {sign}{value:.2f}")
    return "\n".join(out)


def render_csv(order: Order, receipt: Receipt) -> str:
    out = ["sku,name,quantity,unit_price,line_total"]
    for line in order.lines:
        p = line.product
        out.append(f"{p.sku},{p.name},{line.quantity},{p.unit_price:.2f},{line.line_total():.2f}")
    out += [f",,,{label},{value:.2f}" for label, value in _summary(receipt)]
    return "\n".join(out)
