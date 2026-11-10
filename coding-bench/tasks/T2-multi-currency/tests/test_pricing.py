from decimal import Decimal as D

import pytest

from inventory_service.models import Customer, OrderLine, ValidationError
from inventory_service.pricing import compute_order_total, quote, shipping_cost


def lines(catalog, *items):
    return [OrderLine(s, q, catalog.get(s).price) for s, q in items]


def test_simple_order_with_tax_and_shipping(catalog, customers):
    b = compute_order_total(lines(catalog, ("TOO-0001", 2)), catalog, customers["C1"])
    assert b.subtotal == D("25.00")
    assert b.discount_total == D("0")
    assert b.tax == D("1.81")            # 7.25% of 25.00 = 1.8125
    assert b.shipping == D("9.99")       # 1.6 kg
    assert b.total == D("36.80")


def test_category_promo_and_tier(catalog, customers):
    b = compute_order_total(lines(catalog, ("GAR-0001", 2)), catalog, customers["C2"])
    assert b.line_discounts == D("13.50")      # 15% garden promo on 90.00
    assert b.tier_discount == D("3.83")        # silver 5% of 76.50 = 3.825
    assert b.taxable == D("72.67")
    assert b.tax == D("6.45")                  # 8.875% NY
    assert b.shipping == D("15.99")            # 9 kg: 9.99 + 4 started kg above 5 x 1.50
    assert b.total == b.taxable + b.tax + b.shipping


def test_bulk_discount_applies_from_ten_units(catalog, customers):
    b = compute_order_total(lines(catalog, ("KIT-0001", 10)), catalog, customers["C1"])
    assert b.line_discounts == D("3.25")       # 5% of 65.00


def test_bulk_and_promo_do_not_stack(catalog, customers):
    b = compute_order_total(lines(catalog, ("GAR-0002", 12)), catalog, customers["C4"])
    assert b.lines[0]["percent"] == D("15")


def test_coupons(catalog, customers):
    b = compute_order_total(lines(catalog, ("TOO-0002", 1)), catalog, customers["C1"], coupon="save10")
    assert b.coupon_discount == D("8.90")
    b = compute_order_total(lines(catalog, ("TOO-0002", 3)), catalog, customers["C1"], coupon="BIG25")
    assert b.coupon_discount == D("66.75")
    with pytest.raises(ValidationError):
        compute_order_total(lines(catalog, ("KIT-0001", 1)), catalog, customers["C1"], coupon="SAVE10")
    with pytest.raises(ValidationError):
        compute_order_total(lines(catalog, ("KIT-0001", 1)), catalog, customers["C1"], coupon="NOPE")


def test_free_shipping_and_weights():
    assert shipping_cost("0.5", "10") == D("4.99")
    assert shipping_cost("5", "10") == D("9.99")
    assert shipping_cost("5.1", "10") == D("11.49")
    assert shipping_cost("30", "100.00") == D("0")


def test_unknown_region(catalog):
    with pytest.raises(ValidationError):
        quote(catalog, Customer("X", "X", "standard", "MARS"), [("TOO-0001", 1)])
