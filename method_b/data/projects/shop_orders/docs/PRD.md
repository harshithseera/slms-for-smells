# Product Requirements Document: Shop Orders and Checkout

## 1. Overview
A Python package (`shop`) for a small online shop. It manages products and stock,
builds customer orders, prices them with discount rules, customer tiers and tax, adds
shipping, places and cancels orders, and renders invoices as plain text and CSV.
Everything is in memory; there is no UI, network or database.

## 2. Goals
- Never sell stock the shop does not have, even when an order fails halfway.
- Price orders predictably: discount rules, tier discount, tax and shipping are applied
  in a fixed, documented order.
- Produce invoices that the accounting team can read (text) and import (CSV).

## 3. Constraints
- Python 3.12, standard library only.
- Money amounts are `float`s rounded to 2 decimals at each step stated below.

## 4. Functional requirements

### 4.1 Errors (`shop/errors.py`)
`ShopError` is the base class of `UnknownProduct`, `OutOfStock` and `InvalidOrder`.

### 4.2 Products and stock (`shop/products.py`)
- **Product** (dataclass): `sku` (str), `name` (str), `unit_price` (float),
  `category` (str), `weight_kg` (float).
- **Inventory**:
  - `add_product(product, stock=0)`; a duplicate SKU → `ShopError`.
  - `get(sku)` → `Product`; unknown SKU → `UnknownProduct` (also for every method below).
  - `stock(sku)` → units in stock.
  - `restock(sku, quantity)`: quantity must be > 0, otherwise `ValueError`.
  - `reserve(sku, quantity)`: removes units from stock; more than in stock → `OutOfStock`
    (stock unchanged).
  - `release(sku, quantity)`: puts units back.

### 4.3 Orders (`shop/orders.py`)
- **OrderLine** (dataclass): `product`, `quantity`; `line_total()` =
  `unit_price * quantity` rounded to 2 decimals.
- **Order**: `Order(order_id, customer, tier="standard")`. Public attributes `order_id`,
  `customer`, `tier`, `lines` (list of `OrderLine`, in the order they were added) and
  `status`, which is `"open"` for a new order.
  - `add_line(product, quantity)`: quantity ≤ 0 → `InvalidOrder`. Adding a product that is
    already in the order increases that line's quantity instead of adding a new line.
    Lines can only be added while the order is `"open"` (otherwise `InvalidOrder`).
  - `total_weight()` = sum of `weight_kg * quantity` over all lines.

### 4.4 Pricing (`shop/pricing.py`)
- Discount rules, each with `discount_for(line)` → discount amount for one order line:
  - `CategoryDiscount(category, percent)`: `percent`% off lines whose product is in
    `category`.
  - `BulkDiscount(sku, min_quantity, percent)`: `percent`% off the line of product `sku`
    when its quantity is at least `min_quantity`.
- Tier discounts: `standard` 0%, `silver` 2%, `gold` 5%. An unknown tier → `ValueError`
  when the order is priced.
- **PriceBreakdown** (dataclass): `subtotal`, `discount`, `tax`, `total`.
- **PricingEngine(rules=None, tax_rate=0.2)**, `price(order)` → `PriceBreakdown`:
  1. `subtotal` = sum of line totals.
  2. Each line gets the **largest** discount of the rules that apply to it (rules do not
     stack); rounded to 2 decimals per line.
  3. Tier discount = tier percentage of (`subtotal` − line discounts), rounded to 2 decimals.
  4. `discount` = line discounts + tier discount.
  5. `tax` = `tax_rate` × (`subtotal` − `discount`), rounded to 2 decimals.
  6. `total` = `subtotal` − `discount` + `tax`, rounded to 2 decimals.

### 4.5 Shipping (`shop/shipping.py`)
`ShippingCalculator(base_fee=4.99, per_kg=1.5, free_over=100.0)`,
`cost(weight_kg, amount)`: `0.0` if `amount` ≥ `free_over`, otherwise
`base_fee + per_kg * weight_kg` rounded to 2 decimals. `amount` is the discounted,
pre-tax merchandise value (`subtotal − discount`).

### 4.6 Checkout (`shop/checkout.py`)
- **Receipt** (dataclass): `order_id`, `breakdown` (`PriceBreakdown`), `shipping`
  (float), `grand_total` (= `breakdown.total + shipping`, rounded to 2 decimals).
- **CheckoutService(inventory, pricing, shipping)**:
  - `place_order(order)` → `Receipt`:
    - an order without lines, or one that is not `"open"` → `InvalidOrder`;
    - reserves stock for every line. If any line cannot be reserved, everything already
      reserved for this order is released again and `OutOfStock` is raised (the order
      stays `"open"`);
    - prices the order, computes shipping, sets the status to `"placed"`, remembers the
      receipt and returns it.
  - `cancel(order_id)`: only a `"placed"` order can be cancelled, otherwise (including
    unknown ids) `InvalidOrder`. Releases the order's stock and sets the status to
    `"cancelled"`.
  - `get_receipt(order_id)` → the `Receipt` of a placed order; unknown → `InvalidOrder`.

### 4.7 Invoices (`shop/invoices.py`)
`render_text(order, receipt)` → `str`, lines joined with `"\n"`, no trailing newline:
```
Order <order_id>
<product name> x<quantity> @ <unit price> = <line total>      (one per line)
Subtotal: <subtotal>
Discount: -<discount>
Tax: <tax>
Shipping: <shipping>
Total: <grand_total>
```
`render_csv(order, receipt)` → `str`, lines joined with `"\n"`, no trailing newline:
```
sku,name,quantity,unit_price,line_total
<sku>,<name>,<quantity>,<unit price>,<line total>             (one per line)
,,,subtotal,<subtotal>
,,,discount,<discount>
,,,tax,<tax>
,,,shipping,<shipping>
,,,total,<grand_total>
```
All money values in both formats are written with exactly 2 decimals (e.g. `1.50`).

## 5. Non-functional requirements
- Each module has one responsibility; adding a new discount rule type must not require
  changing the pricing engine.
- No global mutable state.
