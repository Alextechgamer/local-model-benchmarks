from decimal import Decimal as D

import pytest


def test_unknown_currency(catalog, customers):
    from inventory_service.currency import UnsupportedCurrency
    from inventory_service.pricing import quote
    with pytest.raises(UnsupportedCurrency):
        quote(catalog, customers["C1"], [("TOO-0001", 1)], currency="CHF")


def test_order_currency_and_usd_refund_only(svc):
    from inventory_service.models import ValidationError
    o = svc.create_order("C3", [("LIT-0001", 1)], currency="jpy")
    assert o.currency == "JPY"
    svc.ship(o.id)
    with pytest.raises(ValidationError):
        svc.refund(o.id, {"LIT-0001": 1})
