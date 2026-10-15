from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_totals(subtotal, discount=Decimal("0.00"), tax_rate=Decimal("0.18")):
    subtotal = money(subtotal)
    discount = min(subtotal, max(Decimal("0.00"), money(discount)))
    taxable = subtotal - discount
    tax = money(taxable * Decimal(str(tax_rate)))
    shipping = Decimal("0.00") if subtotal >= Decimal("999.00") else Decimal("50.00")
    return {
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "shipping": shipping,
        "total": money(taxable + tax + shipping),
    }
