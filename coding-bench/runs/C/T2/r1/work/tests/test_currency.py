from decimal import Decimal as D


def test_convert_to_eur():
    from inventory_service.currency import convert
    assert convert(D("10.00"), "EUR") == D("9.20")


def test_quote_in_eur_keeps_usd_rules(catalog, customers):
    from inventory_service.pricing import quote
    b = quote(catalog, customers["C1"], [("TOO-0001", 2)], currency="EUR")
    assert b.currency == "EUR"
    assert b.subtotal == D("23.00")
    assert b.total == b.taxable + b.tax + b.shipping
