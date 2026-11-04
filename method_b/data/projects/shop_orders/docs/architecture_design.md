# Architecture Design

File tree:
```bash
├── shop
│   ├── __init__.py
│   ├── errors.py
│   ├── products.py
│   ├── orders.py
│   ├── pricing.py
│   ├── shipping.py
│   ├── checkout.py
│   └── invoices.py
```

Layering (a module only imports modules listed before it):
`errors` → `products` → `orders` → `pricing`, `shipping` → `checkout` → `invoices`.

`errors.py`: `ShopError`, `UnknownProduct`, `OutOfStock`, `InvalidOrder`.

`products.py`: `Product` (dataclass); `class Inventory()` with `add_product`, `get`,
`stock`, `restock`, `reserve`, `release`.

`orders.py`: `OrderLine` (dataclass, `line_total()`); `class Order(order_id, customer,
tier="standard")` with `add_line`, `total_weight`.

`pricing.py`: `CategoryDiscount(category, percent)`, `BulkDiscount(sku, min_quantity,
percent)` (both with `discount_for(line)`), `PriceBreakdown` (dataclass),
`class PricingEngine(rules=None, tax_rate=0.2)` with `price(order)`.

`shipping.py`: `class ShippingCalculator(base_fee=4.99, per_kg=1.5, free_over=100.0)` with
`cost(weight_kg, amount)`.

`checkout.py`: `Receipt` (dataclass); `class CheckoutService(inventory, pricing, shipping)`
with `place_order`, `cancel`, `get_receipt`.

`invoices.py`: module-level `render_text(order, receipt)` and `render_csv(order, receipt)`.

Usage example:
```python
from shop.checkout import CheckoutService
from shop.invoices import render_text
from shop.orders import Order
from shop.pricing import BulkDiscount, PricingEngine
from shop.products import Inventory, Product
from shop.shipping import ShippingCalculator

inv = Inventory()
pen = Product("PEN", "Pen", 1.50, "stationery", 0.02)
inv.add_product(pen, stock=100)
svc = CheckoutService(inv, PricingEngine([BulkDiscount("PEN", 10, 20)]), ShippingCalculator())
order = Order("o1", "Ada")
order.add_line(pen, 10)
print(render_text(order, svc.place_order(order)))
```
