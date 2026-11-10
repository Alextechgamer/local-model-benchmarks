from decimal import Decimal as D

import pytest

from inventory_service import reports


def shipped(svc, cid, items, coupon=None):
    o = svc.create_order(cid, items, coupon)
    svc.ship(o.id)
    return o


def test_sales_by_category_counts_kept_units_of_shipped_orders(svc, catalog):
    shipped(svc, "C4", [("TOO-0001", 2), ("GAR-0001", 1)])
    o = shipped(svc, "C4", [("GAR-0002", 3)])
    svc.refund(o.id, {"GAR-0002": 1})
    svc.create_order("C4", [("LIT-0001", 5)])                  # reserved: not counted
    c = svc.create_order("C4", [("KIT-0001", 2)])
    svc.cancel(c.id)                                             # cancelled: not counted
    assert reports.sales_by_category(svc.orders.values(), catalog) == {"garden": D("94.98"), "tools": D("25.00")}


def test_sales_by_category_drops_fully_refunded_categories(svc, catalog):
    o = shipped(svc, "C4", [("TOO-0001", 1), ("KIT-0001", 2)])
    svc.refund(o.id, {"KIT-0001": 2})
    assert reports.sales_by_category(svc.orders.values(), catalog) == {"tools": D("12.50")}


def test_top_products_order_ties_and_n(svc):
    shipped(svc, "C4", [("TOO-0001", 3), ("KIT-0001", 3), ("LIT-0001", 1)])
    shipped(svc, "C4", [("GAR-0002", 5)])
    svc.create_order("C4", [("TOO-0002", 9)])                  # reserved: not counted
    orders = list(svc.orders.values())
    assert reports.top_products(orders, 2) == [("GAR-0002", 5), ("KIT-0001", 3)]
    assert reports.top_products(orders) == [("GAR-0002", 5), ("KIT-0001", 3), ("TOO-0001", 3)]
    assert reports.top_products(orders, 10) == [("GAR-0002", 5), ("KIT-0001", 3), ("TOO-0001", 3), ("LIT-0001", 1)]
    assert reports.top_products(orders, 0) == []
    with pytest.raises(ValueError):
        reports.top_products(orders, -1)


def test_top_products_leaves_out_fully_refunded(svc):
    o = shipped(svc, "C4", [("TOO-0001", 2), ("KIT-0001", 1)])
    svc.refund(o.id, {"TOO-0001": 2})
    assert reports.top_products(svc.orders.values()) == [("KIT-0001", 1)]


def test_inventory_valuation(svc, catalog, inventory):
    inventory.set_stock("TOO-0001", 2)
    catalog.deactivate("TOO-0002")
    expected_active = sum((p.price * inventory.on_hand(p.sku) for p in catalog.products()), D("0"))
    assert reports.inventory_valuation(inventory, catalog) == expected_active
    assert reports.inventory_valuation(inventory, catalog, include_inactive=True) == expected_active + D("89.00") * 50
    assert reports.inventory_valuation(inventory, catalog) == D("5449.50")     # 25 + 2250 + 1249.50 + 1600 + 325


def test_low_stock_report_uses_available_and_threshold(svc, catalog, inventory):
    inventory.set_stock("TOO-0001", 5)
    inventory.set_stock("GAR-0001", 8)
    svc.create_order("C4", [("GAR-0001", 2)])                 # 6 available
    inventory.set_stock("KIT-0001", 6)
    catalog.deactivate("LIT-0001")
    inventory.set_stock("LIT-0001", 0)
    assert reports.low_stock_report(inventory, catalog, threshold=6) == [
        "GAR-0001 Garden Chair: 6 left", "KIT-0001 Mug: 6 left", "TOO-0001 Hammer: 5 left"]
    assert reports.low_stock_report(inventory, catalog) == ["TOO-0001 Hammer: 5 left"]


def test_average_order_value(svc):
    assert reports.average_order_value([]) == D("0.00")
    a = shipped(svc, "C4", [("TOO-0002", 2)])                 # 178.00
    b = shipped(svc, "C4", [("TOO-0001", 1)])                 # 12.50 + 4.99
    svc.create_order("C4", [("TOO-0002", 5)])                 # reserved: not counted
    assert reports.average_order_value(svc.orders.values()) == D("97.75")
    svc.refund(a.id, {"TOO-0002": 1})
    assert reports.average_order_value(svc.orders.values()) == D("53.25")
    svc.refund(b.id, {"TOO-0001": 1})
    assert reports.average_order_value(svc.orders.values()) == D("44.50")
