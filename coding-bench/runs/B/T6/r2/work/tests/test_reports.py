from decimal import Decimal as D

import pytest

from inventory_service.catalog import Catalog
from inventory_service.inventory import Inventory
from inventory_service.models import Order, OrderLine, Refund
from inventory_service.reports import (
    average_order_value,
    inventory_valuation,
    low_stock_report,
    sales_by_category,
    top_products,
    units_sold,
)


def line(sku: str, qty: int, price: str) -> OrderLine:
    return OrderLine(sku, qty, D(price))


def order(oid, lines, status, total=None, refunds=(), region="US-CA"):
    totals = {"total": D(total)} if total is not None else {}
    return Order(oid, "C1", lines, region, None, status, totals, list(refunds))


def refund(rid, oid, quantities, amount):
    return Refund(rid, oid, quantities, D(amount), True)


# units_sold

def test_units_sold_kept_is_bought_minus_refunded(svc):
    o = svc.create_order("C1", [("TOO-0001", 3)])
    svc.ship(o.id)
    assert units_sold(o, "TOO-0001") == 3
    svc.refund(o.id, {"TOO-0001": 1})
    assert units_sold(o, "TOO-0001") == 2
    svc.refund(o.id, {"TOO-0001": 1})
    assert units_sold(o, "TOO-0001") == 1
    assert units_sold(o, "TOO-0002") == 0


# sales_by_category

def test_sales_by_category_counts_only_kept_units_of_counted_orders(svc):
    a = svc.create_order("C1", [("TOO-0001", 2), ("GAR-0002", 1)])
    svc.ship(a.id)
    b = svc.create_order("C1", [("LIT-0001", 1)])
    c = svc.create_order("C1", [("KIT-0001", 4)])
    svc.cancel(c.id)
    out = sales_by_category([a, b, c], svc.catalog)
    assert out == {"tools": D("25.00"), "garden": D("24.99")}
    assert list(out) == ["garden", "tools"]


def test_sales_by_category_refunded_units_do_not_count(svc):
    a = svc.create_order("C4", [("TOO-0002", 2), ("KIT-0001", 2)])
    svc.ship(a.id)
    svc.refund(a.id, {"TOO-0002": 1})
    svc.refund(a.id, {"KIT-0001": 2})
    assert a.status == "partially_refunded"
    out = sales_by_category([a], svc.catalog)
    assert out == {"tools": D("89.00")}
    assert "kitchen" not in out


def test_sales_by_category_full_refund_is_counted_but_contributes_nothing(svc):
    a = svc.create_order("C4", [("KIT-0001", 2)])
    svc.ship(a.id)
    svc.refund(a.id, {"KIT-0001": 2})
    assert a.status == "refunded"
    assert sales_by_category([a], svc.catalog) == {}


def test_sales_by_category_rounds_to_the_cent(catalog):
    o = order("O1", [line("TOO-0001", 3, "1.005")], "shipped")
    assert sales_by_category([o], catalog) == {"tools": D("3.02")}


def test_sales_by_category_accumulates_and_sorts(catalog):
    o1 = order("O1", [line("TOO-0001", 2, "12.50")], "shipped")
    o2 = order("O2", [line("GAR-0001", 2, "45.00"), line("TOO-0002", 1, "89.00")], "shipped")
    o3 = order("O3", [line("LIT-0001", 1, "32.00")], "partially_refunded")
    o4 = order("O4", [line("TOO-0001", 1, "12.50")], "cancelled")
    out = sales_by_category([o1, o2, o3, o4], catalog)
    assert out == {"garden": D("90.00"), "lighting": D("32.00"), "tools": D("114.00")}
    assert list(out) == ["garden", "lighting", "tools"]


def test_sales_by_category_no_orders(catalog):
    assert sales_by_category([], catalog) == {}


# top_products

def test_top_products_ranks_by_units_kept(catalog):
    o1 = order("O1", [line("TOO-0001", 5, "12.50")], "shipped")
    o2 = order("O2", [line("TOO-0001", 2, "12.50"), line("GAR-0001", 3, "45.00")], "shipped",
               refunds=[refund("F1", "O2", {"TOO-0001": 1}, "12.50")])
    o3 = order("O3", [line("KIT-0001", 9, "6.50")], "reserved")
    o4 = order("O4", [line("LIT-0001", 3, "32.00"), line("GAR-0002", 3, "24.99")], "shipped")
    orders = [o1, o2, o3, o4]
    assert top_products(orders) == [("TOO-0001", 6), ("GAR-0001", 3), ("GAR-0002", 3)]
    assert top_products(orders, n=2) == [("TOO-0001", 6), ("GAR-0001", 3)]
    assert top_products(orders, n=10) == [("TOO-0001", 6), ("GAR-0001", 3), ("GAR-0002", 3), ("LIT-0001", 3)]


def test_top_products_excludes_fully_refunded_skus(catalog):
    o1 = order("O1", [line("TOO-0001", 1, "12.50"), line("TOO-0002", 2, "89.00")], "refunded",
               refunds=[refund("F1", "O1", {"TOO-0001": 1, "TOO-0002": 2}, "200.00")])
    o2 = order("O2", [line("GAR-0001", 1, "45.00")], "shipped")
    assert top_products([o1, o2], n=5) == [("GAR-0001", 1)]


def test_top_products_zero_and_negative_n(catalog):
    o = order("O1", [line("TOO-0001", 1, "12.50")], "shipped")
    assert top_products([o], n=0) == []
    with pytest.raises(ValueError):
        top_products([o], n=-1)


def test_top_products_empty(catalog):
    assert top_products([], n=3) == []


# inventory_valuation

def _base_valuation(clock):
    c = Catalog()
    for sku, name, price in [("AAA-0001", "One", "10.00"), ("BBB-0002", "Two", "20.00"),
                             ("CCC-0003", "Three", "30.00")]:
        c.add_product(sku, name, price, "misc", "0")
    inv = Inventory(clock)
    inv.receive("AAA-0001", 1)
    inv.receive("BBB-0002", 2)
    inv.receive("CCC-0003", 3)
    inv.receive("ZZZ-9999", 10)
    inv.reserve("O1", "AAA-0001", 1)
    return c, inv


def test_inventory_valuation_on_hand_times_price(clock):
    c, inv = _base_valuation(clock)
    assert inventory_valuation(inv, c) == D("140.00")


def test_inventory_valuation_inactive_only_when_asked(clock):
    c, inv = _base_valuation(clock)
    c.deactivate("BBB-0002")
    assert inventory_valuation(inv, c) == D("100.00")
    assert inventory_valuation(inv, c, include_inactive=True) == D("140.00")


def test_inventory_valuation_rounds_to_the_cent(clock):
    c = Catalog()
    c.add_product("AAA-0001", "Widget", "1.005", "misc", "0")
    inv = Inventory(clock)
    inv.receive("AAA-0001", 3)
    assert inventory_valuation(inv, c) == D("3.02")


def test_inventory_valuation_empty(clock):
    assert inventory_valuation(Inventory(clock), Catalog()) == D("0.00")


# low_stock_report

def test_low_stock_report_at_or_below_threshold(catalog, inventory):
    inventory.set_stock("TOO-0001", 4)
    inventory.set_stock("GAR-0002", 5)
    assert low_stock_report(inventory, catalog) == ["GAR-0002 Hose 20m: 5 left", "TOO-0001 Hammer: 4 left"]


def test_low_stock_report_uses_available_units(catalog, inventory):
    inventory.reserve("O1", "TOO-0001", 47)
    assert low_stock_report(inventory, catalog) == ["TOO-0001 Hammer: 3 left"]


def test_low_stock_report_skips_inactive(catalog, inventory):
    inventory.set_stock("TOO-0001", 1)
    catalog.deactivate("TOO-0001")
    assert low_stock_report(inventory, catalog) == []


def test_low_stock_report_custom_threshold(catalog, inventory):
    inventory.set_stock("TOO-0001", 8)
    assert low_stock_report(inventory, catalog, threshold=10) == ["TOO-0001 Hammer: 8 left"]
    assert low_stock_report(inventory, catalog, threshold=7) == []


def test_low_stock_report_default_threshold_is_five(catalog, inventory):
    inventory.set_stock("TOO-0001", 6)
    assert low_stock_report(inventory, catalog) == []
    inventory.set_stock("TOO-0001", 5)
    assert low_stock_report(inventory, catalog) == ["TOO-0001 Hammer: 5 left"]


# average_order_value

def test_average_order_value_no_orders():
    assert average_order_value([]) == D("0.00")


def test_average_order_value_mean_of_total_minus_refunded(catalog):
    shipped = order("O1", [line("TOO-0001", 2, "12.50")], "shipped", total="100.00")
    partial = order("O2", [line("TOO-0001", 1, "12.50")], "partially_refunded", total="50.00",
                    refunds=[refund("F1", "O2", {"TOO-0001": 1}, "20.00")])
    reserved = order("O3", [line("TOO-0001", 9, "12.50")], "reserved", total="999.00")
    cancelled = order("O4", [line("TOO-0001", 9, "12.50")], "cancelled", total="999.00")
    refunded = order("O5", [line("TOO-0001", 1, "12.50")], "refunded", total="30.00",
                     refunds=[refund("F2", "O5", {"TOO-0001": 1}, "30.00")])
    assert average_order_value([shipped, partial, reserved, cancelled, refunded]) == D("43.33")


def test_average_order_value_rounds_half_up(catalog):
    a = order("O1", [line("TOO-0001", 1, "12.50")], "shipped", total="10.00")
    b = order("O2", [line("TOO-0001", 1, "12.50")], "shipped", total="10.01")
    assert average_order_value([a, b]) == D("10.01")


def test_average_order_value_end_to_end(svc):
    o1 = svc.create_order("C4", [("TOO-0002", 1)])
    svc.ship(o1.id)
    o2 = svc.create_order("C4", [("KIT-0001", 2)])
    svc.ship(o2.id)
    assert o1.totals["total"] == D("98.99")
    assert o2.totals["total"] == D("17.99")
    assert average_order_value([o1, o2]) == D("58.49")
