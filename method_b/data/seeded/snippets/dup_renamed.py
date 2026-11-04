def invoice_total(items, tax_rate):
    subtotal = 0.0
    for item in items:
        if item["qty"] <= 0:
            continue
        subtotal += item["qty"] * item["unit_price"]
    tax = subtotal * tax_rate
    return round(subtotal + tax, 2)


def quote_amount(lines, vat):
    amount = 0.0
    for line in lines:
        if line["qty"] <= 0:
            continue
        amount += line["qty"] * line["unit_price"]
    extra = amount * vat
    return round(amount + extra, 2)
