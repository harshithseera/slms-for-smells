# UML sequence

```mermaid
sequenceDiagram
    participant Client
    participant CS as CheckoutService
    participant Inv as Inventory
    participant PE as PricingEngine
    participant SC as ShippingCalculator
    participant Doc as Invoices

    Client->>CS: place_order(order)
    CS->>CS: order has lines and status == "open"?
    loop each order line
        CS->>Inv: reserve(sku, quantity)
        alt OutOfStock
            CS->>Inv: release(...) for lines already reserved
            CS-->>Client: raise OutOfStock
        end
    end
    CS->>PE: price(order)
    PE->>PE: subtotal, best rule discount per line, tier discount, tax, total
    PE-->>CS: PriceBreakdown
    CS->>SC: cost(order.total_weight(), subtotal - discount)
    SC-->>CS: shipping
    CS->>CS: status = "placed"; store Receipt
    CS-->>Client: Receipt

    Client->>Doc: render_text(order, receipt) / render_csv(order, receipt)
    Doc-->>Client: invoice string

    Client->>CS: cancel(order_id)
    CS->>Inv: release(sku, quantity) for each line
    CS-->>Client: status = "cancelled"
```
