from decimal import Decimal as D

import pytest

from inventory_service import reports
from inventory_service.catalog import Catalog
from inventory_service.inventory import Inventory
from inventory_service.models import Order, OrderLine, Refund


def line(sku, qty, price="10.00"):
    return OrderLine(sku, qty, D(price))


def order(oid, status, lines, total, refunds=()):
    return Order(oid, "C1", lines, "US-CA", None, status, {"total": D(total)}, list(refunds))


# --- units_sold -----------------------------------------------------------


def test_units_sold_no_refund(catalog):
    o = order("O1", "shipped", [line("TOO-0001", 3, "12.50")], "40")
    assert reports.units_sold(o, "TOO-0001") == 3


def test_units_sold_partial_refund(catalog):
    o = order("O1", "partially_refunded", [line("TOO-0001", 5, "12.50")], "60",
              refunds=[Refund("F1", "O1", {"TOO-0001": 2}, D("25.00"), True)])
    assert reports.units_sold(o, "TOO-0001") == 3


def test_units_sold_multiple_refunds(catalog):
    o = order("O1", "partially_refunded", [line("TOO-0001", 5, "12.50")], "60",
              refunds=[Refund("F1", "O1", {"TOO-0001": 1}, D("12.50"), True),
                       Refund("F2", "O1", {"TOO-0001": 2}, D("25.00"), True)])
    assert reports.units_sold(o, "TOO-0001") == 2


def test_units_sold_fully_refunded(catalog):
    o = order("O1", "refunded", [line("TOO-0001", 2, "12.50")], "25",
              refunds=[Refund("F1", "O1", {"TOO-0001": 2}, D("25.00"), True)])
    assert reports.units_sold(o, "TOO-0001") == 0


def test_units_sold_sku_not_on_order(catalog):
    o = order("O1", "shipped", [line("TOO-0001", 3, "12.50")], "40")
    assert reports.units_sold(o, "GAR-0001") == 0


# --- sales_by_category ----------------------------------------------------


def _big_orders(catalog):
    shipped = order("O1", "shipped", [line("TOO-0001", 2, "12.50"), line("GAR-0002", 3, "24.99"),
                                      line("KIT-0001", 1, "6.50")], "106")
    partial = order("O2", "partially_refunded", [line("GAR-0001", 2, "45.00"), line("TOO-0002", 1, "89.00")], "134",
                    refunds=[Refund("F1", "O2", {"GAR-0001": 1}, D("40.00"), True)])
    reserved = order("O3", "reserved", [line("LIT-0001", 2, "32.00")], "64")
    cancelled = order("O4", "cancelled", [line("TOO-0002", 2, "89.00")], "178")
    refunded = order("O5", "refunded", [line("LIT-0001", 2, "32.00")], "64",
                     refunds=[Refund("F2", "O5", {"LIT-0001": 2}, D("64.00"), True)])
    return [shipped, partial, reserved, cancelled, refunded]


def test_sales_by_category_counts_kept_units(catalog):
    out = reports.sales_by_category(_big_orders(catalog), catalog)
    assert out == {"garden": D("119.97"), "kitchen": D("6.50"), "tools": D("114.00")}


def test_sales_by_category_sorted_by_category(catalog):
    out = reports.sales_by_category(_big_orders(catalog), catalog)
    assert list(out) == ["garden", "kitchen", "tools"]


def test_sales_by_category_ignores_reserved_and_cancelled(catalog):
    shipped = order("O1", "shipped", [line("KIT-0001", 1, "6.50")], "6.50")
    reserved = order("O2", "reserved", [line("LIT-0001", 2, "32.00")], "64")
    cancelled = order("O3", "cancelled", [line("TOO-0002", 2, "89.00")], "178")
    out = reports.sales_by_category([shipped, reserved, cancelled], catalog)
    assert out == {"kitchen": D("6.50")}


def test_sales_by_category_omits_categories_without_sales(catalog):
    o = order("O1", "refunded", [line("LIT-0001", 2, "32.00")], "64",
              refunds=[Refund("F1", "O1", {"LIT-0001": 2}, D("64.00"), True)])
    assert reports.sales_by_category([o], catalog) == {}


def test_sales_by_category_uses_unit_price_times_kept(catalog):
    o = order("O1", "partially_refunded", [OrderLine("TOO-0001", 5, D("0.335"))], "2",
              refunds=[Refund("F1", "O1", {"TOO-0001": 2}, D("1"), True)])
    out = reports.sales_by_category([o], catalog)
    assert out == {"tools": D("1.01")}  # 0.335 x 3 kept = 1.005, rounded half-up


def test_sales_by_category_empty(catalog):
    assert reports.sales_by_category([], catalog) == {}


# --- top_products ---------------------------------------------------------


def test_top_products_ranking(catalog):
    o1 = order("O1", "shipped", [line("TOO-0001", 3), line("GAR-0002", 1)], "40")
    o2 = order("O2", "partially_refunded", [line("TOO-0001", 2), line("KIT-0001", 2)], "30",
               refunds=[Refund("F1", "O2", {"TOO-0001": 1}, D("10"), True)])
    o3 = order("O3", "reserved", [line("LIT-0001", 9)], "90")
    o4 = order("O4", "cancelled", [line("TOO-0002", 9)], "90")
    o5 = order("O5", "refunded", [line("GAR-0001", 4)], "40",
               refunds=[Refund("F2", "O5", {"GAR-0001": 4}, D("40"), True)])
    assert reports.top_products([o1, o2, o3, o4, o5]) == [("TOO-0001", 4), ("KIT-0001", 2), ("GAR-0002", 1)]


def test_top_products_default_n_is_three(catalog):
    o = order("O1", "shipped", [line("TOO-0001", 1), line("GAR-0002", 2), line("KIT-0001", 3),
                                line("GAR-0001", 4)], "40")
    assert reports.top_products([o]) == [("GAR-0001", 4), ("KIT-0001", 3), ("GAR-0002", 2)]


def test_top_products_ties_by_sku(catalog):
    o = order("O1", "shipped", [line("TOO-0001", 2), line("GAR-0002", 2)], "30")
    assert reports.top_products([o], 2) == [("GAR-0002", 2), ("TOO-0001", 2)]


def test_top_products_excludes_fully_refunded(catalog):
    o = order("O1", "refunded", [line("GAR-0001", 4)], "40",
              refunds=[Refund("F1", "O1", {"GAR-0001": 4}, D("40"), True)])
    assert reports.top_products([o]) == []


def test_top_products_n_larger_than_sku_count(catalog):
    o = order("O1", "shipped", [line("TOO-0001", 1), line("GAR-0002", 2)], "30")
    assert reports.top_products([o], 10) == [("GAR-0002", 2), ("TOO-0001", 1)]


def test_top_products_zero(catalog):
    o = order("O1", "shipped", [line("TOO-0001", 1)], "10")
    assert reports.top_products([o], 0) == []


def test_top_products_negative_n(catalog):
    with pytest.raises(ValueError):
        reports.top_products([], -1)


# --- inventory_valuation --------------------------------------------------


def test_inventory_valuation_active_products(catalog, inventory):
    assert reports.inventory_valuation(inventory, catalog) == D("10499.50")  # 209.99 x 50


def test_inventory_valuation_omits_inactive_by_default(catalog, inventory):
    catalog.deactivate("GAR-0001")
    assert reports.inventory_valuation(inventory, catalog) == D("8249.50")
    assert reports.inventory_valuation(inventory, catalog, include_inactive=True) == D("10499.50")


def test_inventory_valuation_uses_on_hand(catalog, inventory):
    inventory.reserve("O1", "TOO-0001", 10)
    assert inventory.available("TOO-0001") == 40
    assert reports.inventory_valuation(inventory, catalog) == D("10499.50")


def test_inventory_valuation_ignores_unknown_skus(catalog, inventory):
    inventory.receive("ZZZ-9999", 7)
    assert reports.inventory_valuation(inventory, catalog) == D("10499.50")


def test_inventory_valuation_rounds_to_cent():
    cat = Catalog()
    cat.add_product("AAA-0001", "Tiny", "0.335", "misc")
    inv = Inventory()
    inv.receive("AAA-0001", 3)
    assert reports.inventory_valuation(inv, cat) == D("1.01")  # 1.005 half-up


def test_inventory_valuation_empty(catalog):
    assert reports.inventory_valuation(Inventory(), catalog) == D("0.00")


# --- low_stock_report -----------------------------------------------------


def _low_stock_setup():
    cat = Catalog()
    for sku, name in [("AAA-0001", "Alpha"), ("AAA-0002", "Bravo"), ("AAA-0003", "Charlie"),
                      ("AAA-0004", "Delta"), ("AAA-0005", "Echo")]:
        cat.add_product(sku, name, "10.00", "misc")
    inv = Inventory()
    inv.receive("AAA-0001", 3)
    inv.receive("AAA-0002", 5)
    inv.receive("AAA-0003", 6)
    inv.receive("AAA-0004", 10)
    inv.receive("AAA-0005", 2)
    inv.reserve("O1", "AAA-0004", 6)
    cat.deactivate("AAA-0005")
    return cat, inv


def test_low_stock_report_default_threshold():
    cat, inv = _low_stock_setup()
    assert reports.low_stock_report(inv, cat) == [
        "AAA-0001 Alpha: 3 left",
        "AAA-0002 Bravo: 5 left",
        "AAA-0004 Delta: 4 left",
    ]


def test_low_stock_report_uses_available_not_on_hand():
    cat, inv = _low_stock_setup()
    out = reports.low_stock_report(inv, cat)
    assert "AAA-0004 Delta: 4 left" in out


def test_low_stock_report_custom_threshold():
    cat, inv = _low_stock_setup()
    assert reports.low_stock_report(inv, cat, threshold=4) == [
        "AAA-0001 Alpha: 3 left",
        "AAA-0004 Delta: 4 left",
    ]
    assert reports.low_stock_report(inv, cat, threshold=0) == []


def test_low_stock_report_omits_inactive():
    cat, inv = _low_stock_setup()
    assert not any("Echo" in l for l in reports.low_stock_report(inv, cat, threshold=10))


def test_low_stock_report_all_stocked():
    cat, inv = _low_stock_setup()
    assert reports.low_stock_report(inv, cat, threshold=0) == []


# --- average_order_value --------------------------------------------------


def test_average_order_value_empty():
    assert reports.average_order_value([]) == D("0.00")


def test_average_order_value_counts_kept_amounts():
    o1 = order("O1", "shipped", [line("TOO-0001", 1)], "90.00")
    o2 = order("O2", "partially_refunded", [line("TOO-0002", 1)], "200.00",
               refunds=[Refund("F1", "O2", {"TOO-0002": 1}, D("50.00"), True)])
    o3 = order("O3", "refunded", [line("TOO-0002", 1)], "300.00",
               refunds=[Refund("F2", "O3", {"TOO-0002": 1}, D("300.00"), True)])
    o4 = order("O4", "reserved", [line("TOO-0002", 1)], "999.00")
    o5 = order("O5", "cancelled", [line("TOO-0002", 1)], "888.00")
    assert reports.average_order_value([o1, o2, o3, o4, o5]) == D("80.00")  # (90 + 150 + 0) / 3


def test_average_order_value_rounds_to_cent():
    o1 = order("O1", "shipped", [line("TOO-0001", 1)], "10.00")
    o2 = order("O2", "shipped", [line("TOO-0001", 1)], "10.01")
    assert reports.average_order_value([o1, o2]) == D("10.01")  # 10.005 half-up
