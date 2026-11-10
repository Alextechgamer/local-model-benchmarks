from decimal import Decimal as D

import pytest

from inventory_service.models import Order, OrderLine, Refund
from inventory_service.reports import (average_order_value, inventory_valuation, low_stock_report,
                                       sales_by_category, top_products, units_sold)


def mk_order(oid, status, items, refunds=(), total="0"):
    lines = [OrderLine(sku, qty, D(price)) for sku, qty, price in items]
    refund_list = [Refund(f"F{i}", oid, q, D(amount), True) for i, (q, amount) in enumerate(refunds)]
    return Order(oid, "C1", lines, "US-CA", None, status, {"total": D(total)}, refund_list)


def test_units_sold_subtracts_refunded_units():
    o = mk_order("O1", "partially_refunded", [("TOO-0001", 3, "12.50")], [({"TOO-0001": 2}, "25.00")])
    assert units_sold(o, "TOO-0001") == 1
    assert units_sold(o, "KIT-0001") == 0


def test_sales_by_category_counts_only_shipped_and_refunded(catalog):
    orders = [
        # shipped: tools
        mk_order("O1", "shipped", [("TOO-0001", 2, "12.50")]),
        # partially refunded: 1 drill kept; the fully refunded chair line leaves no sales and no garden category
        mk_order("O2", "partially_refunded", [("TOO-0002", 2, "89.00"), ("GAR-0001", 1, "45.00")],
                 [({"TOO-0002": 1}, "89.00"), ({"GAR-0001": 1}, "45.00")]),
        # status refunded with a unit kept: kitchen counts
        mk_order("O3", "refunded", [("KIT-0001", 2, "6.50")], [({"KIT-0001": 1}, "6.50")]),
        # cancelled and still-reserved orders do not count
        mk_order("O4", "cancelled", [("LIT-0001", 3, "32.00")]),
        mk_order("O5", "reserved", [("GAR-0002", 1, "24.99")]),
    ]
    out = sales_by_category(orders, catalog)
    assert out == {"kitchen": D("6.50"), "tools": D("114.00")}
    assert list(out) == ["kitchen", "tools"]


def test_sales_by_category_rounds_to_the_cent(catalog):
    out = sales_by_category([mk_order("O1", "shipped", [("TOO-0001", 1, "4.005")])], catalog)
    assert out == {"tools": D("4.01")}


def test_sales_by_category_sums_the_same_category_across_orders(catalog):
    orders = [
        mk_order("O1", "shipped", [("TOO-0001", 2, "12.50")]),
        mk_order("O2", "shipped", [("TOO-0002", 1, "89.00")]),
    ]
    assert sales_by_category(orders, catalog) == {"tools": D("114.00")}


def test_top_products_ranks_units_kept_with_alpha_ties(catalog):
    orders = [
        mk_order("O1", "shipped", [("TOO-0001", 1, "12.50"), ("KIT-0002", 1, "6.50")]),
        mk_order("O2", "shipped", [("TOO-0001", 1, "12.50"), ("LIT-0001", 1, "32.00")]),
        # fully refunded SKU is left out; the cancelled order's lamps do not count
        mk_order("O3", "partially_refunded", [("TOO-0002", 2, "89.00"), ("GAR-0001", 3, "45.00")],
                 [({"TOO-0002": 2}, "178.00")]),
        mk_order("O4", "cancelled", [("LIT-0001", 5, "32.00")]),
    ]
    assert top_products(orders) == [("GAR-0001", 3), ("TOO-0001", 2), ("KIT-0002", 1)]
    assert top_products(orders, 2) == [("GAR-0001", 3), ("TOO-0001", 2)]
    assert top_products(orders, 0) == []
    assert top_products(orders, 10) == [("GAR-0001", 3), ("TOO-0001", 2), ("KIT-0002", 1), ("LIT-0001", 1)]
    with pytest.raises(ValueError):
        top_products(orders, -1)


def test_inventory_valuation_uses_catalog_prices_and_stock(catalog, inventory):
    assert inventory_valuation(inventory, catalog) == D("10499.50")


def test_inventory_valuation_inactive_products_only_when_asked(catalog, inventory):
    catalog.deactivate("LIT-0001")
    assert inventory_valuation(inventory, catalog) == D("8899.50")
    assert inventory_valuation(inventory, catalog, include_inactive=True) == D("10499.50")


def test_inventory_valuation_ignores_stock_not_in_catalog_and_rounds(catalog, inventory):
    inventory.receive("ZZZ-9999", 100)
    catalog.add_product("KIT-0009", "Odd Part", "0.005", "kitchen")
    inventory.receive("KIT-0009", 1)
    assert inventory_valuation(inventory, catalog) == D("10499.51")


def test_low_stock_report_lists_active_products_at_or_below_threshold(catalog, inventory):
    inventory.set_stock("GAR-0002", 5)                 # exactly at the default threshold: in
    inventory.set_stock("TOO-0001", 8)
    inventory.reserve("O1", "TOO-0001", 3)             # available 5, on-hand 8: in
    inventory.set_stock("LIT-0001", 6)                # available 6: out
    inventory.set_stock("KIT-0001", 2)
    catalog.deactivate("KIT-0001")                     # inactive but low: must not be listed
    assert low_stock_report(inventory, catalog) == ["GAR-0002 Hose 20m: 5 left", "TOO-0001 Hammer: 5 left"]
    assert low_stock_report(inventory, catalog, threshold=6) == [
        "GAR-0002 Hose 20m: 5 left",
        "LIT-0001 Desk Lamp: 6 left",
        "TOO-0001 Hammer: 5 left",
    ]


def test_average_order_value_ignores_cancelled_and_reserved_orders():
    orders = [
        mk_order("O1", "shipped", [("TOO-0001", 1, "12.50")], total="10.00"),
        mk_order("O2", "partially_refunded", [("TOO-0002", 1, "89.00")],
                 [({"TOO-0002": 0}, "0.05")], total="20.05"),
        mk_order("O3", "cancelled", [("LIT-0001", 1, "32.00")], total="999.00"),
        mk_order("O4", "reserved", [("KIT-0001", 1, "6.50")], total="888.00"),
    ]
    assert average_order_value(orders) == D("15.00")


def test_average_order_value_rounds_to_the_cent():
    orders = [
        mk_order("O1", "shipped", [], total="10.00"),
        mk_order("O2", "shipped", [], total="10.01"),
    ]
    assert average_order_value(orders) == D("10.01")


def test_average_order_value_is_zero_without_counted_orders():
    assert average_order_value([]) == D("0.00")
    assert average_order_value([mk_order("O1", "cancelled", [], total="999.00")]) == D("0.00")
