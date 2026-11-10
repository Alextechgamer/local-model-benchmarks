from decimal import Decimal as D

import pytest

from inventory_service.catalog import Catalog
from inventory_service.inventory import Inventory
from inventory_service.models import Order, OrderLine, Refund, Customer
from inventory_service.orders import OrderService
from inventory_service.reports import (average_order_value, inventory_valuation, low_stock_report,
                                       sales_by_category, top_products, units_sold)

PRODUCTS = [
    ("TOO-0001", "Hammer", "12.50", "tools", "0.8"),
    ("TOO-0002", "Cordless Drill", "89.00", "tools", "1.9"),
    ("GAR-0001", "Garden Chair", "45.00", "garden", "4.5"),
    ("GAR-0002", "Hose 20m", "24.99", "garden", "2.2"),
    ("LIT-0001", "Desk Lamp", "32.00", "lighting", "1.1"),
    ("KIT-0001", "Mug", "6.50", "kitchen", "0.35"),
]

CUSTOMERS = [
    Customer("C1", "Ann", "standard", "US-CA"),
    Customer("C4", "Dan", "standard", "US-OR"),
]


@pytest.fixture
def catalog():
    c = Catalog()
    for p in PRODUCTS:
        c.add_product(*p)
    return c


@pytest.fixture
def inventory():
    inv = Inventory()
    for p in PRODUCTS:
        inv.receive(p[0], 50)
    return inv


@pytest.fixture
def svc(catalog, inventory):
    customers = {c.id: c for c in CUSTOMERS}
    return OrderService(catalog, inventory, customers)


def mk_order(oid, status, items, refund_specs=(), total="999.00"):
    lines = [OrderLine(sku, qty, price) for sku, qty, price in items]
    refunds = [Refund(f"F{i + 1}", oid, dict(qty), amount, True)
               for i, (qty, amount) in enumerate(refund_specs)]
    return Order(oid, "C1", lines, "US-CA", None, status, {"total": D(total)}, refunds)


# ---------------- units_sold ----------------

def test_units_sold_bought_minus_refunded():
    order = mk_order("O1", "shipped", [("TOO-0001", 3, D("12.50")), ("KIT-0001", 2, D("6.50"))],
                     [({"TOO-0001": 2}, D("25.00")), ({"KIT-0001": 1}, D("6.50"))])
    assert units_sold(order, "TOO-0001") == 1
    assert units_sold(order, "KIT-0001") == 1
    assert units_sold(order, "LIT-0001") == 0


def test_units_sold_sums_lines_and_refunds():
    order = mk_order("O2", "shipped", [("TOO-0001", 3, D("12.50"))],
                     [({"TOO-0001": 1}, D("12.50")), ({"TOO-0001": 1}, D("12.50"))])
    assert units_sold(order, "TOO-0001") == 1
    assert units_sold(mk_order("O3", "shipped", [("KIT-0001", 4, D("6.50"))]), "KIT-0001") == 4


# ---------------- sales_by_category ----------------

def test_sales_skips_reserved_and_cancelled_orders(svc):
    o1 = svc.create_order("C1", [("TOO-0001", 2), ("GAR-0001", 3)])
    svc.ship(o1.id)
    o2 = svc.create_order("C4", [("KIT-0001", 4)])
    svc.ship(o2.id)
    svc.refund(o2.id, {"KIT-0001": 2})
    o3 = svc.create_order("C1", [("LIT-0001", 1)])
    svc.cancel(o3.id)
    o4 = svc.create_order("C4", [("KIT-0001", 7)])  # still reserved
    o5 = svc.create_order("C1", [("TOO-0001", 1)])
    svc.ship(o5.id)

    out = sales_by_category([o1, o2, o3, o4, o5], svc.catalog)
    assert list(out) == ["garden", "kitchen", "tools"]  # sorted by category
    assert out == {"garden": D("135.00"), "kitchen": D("13.00"), "tools": D("37.50")}
    assert "lighting" not in out  # cancelled order does not count


def test_sales_only_kept_units_count(svc):
    o = svc.create_order("C1", [("TOO-0001", 4)])
    svc.ship(o.id)
    svc.refund(o.id, {"TOO-0001": 3})
    out = sales_by_category([o], svc.catalog)
    assert out == {"tools": D("12.50")}  # 1 kept unit at the line's unit price


def test_sales_counts_refunded_and_partially_refunded_orders(svc):
    shipped = svc.create_order("C4", [("TOO-0002", 2)])
    svc.ship(shipped.id)
    svc.refund(shipped.id, {"TOO-0002": 1})  # partially_refunded
    full = mk_order("F9", "refunded", [("TOO-0002", 1, D("89.00")), ("KIT-0001", 2, D("6.50"))],
                    [({"TOO-0002": 1}, D("89.00")), ({"KIT-0001": 1}, D("6.50"))])

    out = sales_by_category([shipped, full], svc.catalog)
    assert out == {"tools": D("89.00"), "kitchen": D("6.50")}


def test_sales_uses_line_price_not_catalog_price(catalog):
    order = mk_order("O9", "refunded", [("TOO-0002", 1, D("80.00")), ("KIT-0001", 1, D("5.55"))],
                     [({"TOO-0002": 1}, D("80.00"))])
    out = sales_by_category([order], catalog)
    assert out == {"kitchen": D("5.55")}  # the fully refunded line is left out


def test_sales_rounded_to_the_cent(catalog):
    order = mk_order("O8", "shipped", [("TOO-0001", 3, D("10.005"))])
    out = sales_by_category([order], catalog)
    assert out == {"tools": D("30.02")}  # 3 x 10.005 = 30.015, half-up


# ---------------- top_products ----------------

def test_top_products_ranking(svc):
    a1 = svc.create_order("C1", [("TOO-0001", 4)])
    svc.ship(a1.id)
    a2 = svc.create_order("C1", [("GAR-0001", 4)])
    svc.ship(a2.id)
    a3 = svc.create_order("C1", [("KIT-0001", 3)])
    svc.ship(a3.id)
    svc.refund(a3.id, {"KIT-0001": 2})
    a4 = svc.create_order("C1", [("LIT-0001", 2)])
    svc.ship(a4.id)
    svc.refund(a4.id, {"LIT-0001": 1})
    svc.refund(a4.id, {"LIT-0001": 1})  # fully refunded -> left out
    a5 = svc.create_order("C4", [("GAR-0002", 9)])
    svc.cancel(a5.id)

    orders = [a1, a2, a3, a4, a5]
    assert top_products(orders) == [("GAR-0001", 4), ("TOO-0001", 4), ("KIT-0001", 1)]
    assert top_products(orders, 2) == [("GAR-0001", 4), ("TOO-0001", 4)]  # ties by SKU A-Z
    assert top_products(orders, 0) == []
    assert top_products(orders, 99) == [("GAR-0001", 4), ("TOO-0001", 4), ("KIT-0001", 1)]
    with pytest.raises(ValueError, match="n cannot be negative"):
        top_products(orders, -1)


# ---------------- inventory_valuation ----------------

def test_inventory_valuation_uses_on_hand(inventory, catalog):
    inventory.reserve("O1", "TOO-0002", 5)
    assert inventory_valuation(inventory, catalog) == D("10499.50")


def test_inventory_valuation_inactive_only_when_asked(inventory, catalog):
    catalog.deactivate("GAR-0001")
    assert inventory_valuation(inventory, catalog) == D("8249.50")
    assert inventory_valuation(inventory, catalog, include_inactive=True) == D("10499.50")


def test_inventory_valuation_rounds_to_the_cent(inventory, catalog):
    catalog.update_price("KIT-0001", "6.5009")
    assert inventory_valuation(inventory, catalog) == D("10499.55")  # 50 x 6.5009 = 325.045


# ---------------- low_stock_report ----------------

def test_low_stock_report_default_threshold(inventory, catalog):
    inventory.set_stock("TOO-0001", 5)   # exactly at the threshold: included
    inventory.set_stock("TOO-0002", 6)   # above: excluded
    inventory.set_stock("GAR-0001", 4)
    inventory.reserve("O1", "GAR-0001", 1)  # 3 available even though 4 are on hand
    inventory.set_stock("GAR-0002", 0)
    catalog.deactivate("GAR-0002")       # inactive products are never listed
    inventory.set_stock("LIT-0001", 100)
    inventory.set_stock("KIT-0001", 100)
    assert low_stock_report(inventory, catalog) == ["GAR-0001 Garden Chair: 3 left",
                                                    "TOO-0001 Hammer: 5 left"]


def test_low_stock_report_explicit_threshold(inventory, catalog):
    inventory.set_stock("TOO-0001", 5)
    inventory.set_stock("TOO-0002", 6)
    inventory.set_stock("GAR-0001", 3)
    for sku in ("GAR-0002", "LIT-0001", "KIT-0001"):
        inventory.set_stock(sku, 100)
    assert low_stock_report(inventory, catalog, threshold=3) == ["GAR-0001 Garden Chair: 3 left"]
    assert low_stock_report(inventory, catalog, threshold=6) == ["GAR-0001 Garden Chair: 3 left",
                                                                 "TOO-0001 Hammer: 5 left",
                                                                 "TOO-0002 Cordless Drill: 6 left"]


# ---------------- average_order_value ----------------

def test_average_order_value_skips_uncounted_statuses():
    shipped = mk_order("S1", "shipped", [("TOO-0001", 1, D("12.50"))], total="10.00")
    partial = mk_order("S2", "partially_refunded", [("TOO-0001", 2, D("12.50"))],
                       [({"TOO-0001": 1}, D("0.01"))], total="10.01")
    refunded = mk_order("S3", "refunded", [("TOO-0001", 1, D("12.50"))],
                        [({"TOO-0001": 1}, D("30.03"))], total="30.03")
    reserved = mk_order("S4", "reserved", [("TOO-0001", 1, D("12.50"))])
    cancelled = mk_order("S5", "cancelled", [("TOO-0001", 1, D("12.50"))])
    assert average_order_value([shipped, partial, refunded, reserved, cancelled]) == D("6.67")
    empty = average_order_value([reserved, cancelled])
    assert str(empty) == "0.00"


def test_average_order_value_rounds_half_up():
    a = mk_order("A1", "shipped", [("TOO-0001", 1, D("12.50"))], total="10.00")
    b = mk_order("A2", "shipped", [("TOO-0001", 1, D("12.50"))], total="10.01")
    assert average_order_value([a, b]) == D("10.01")  # (10.00 + 10.01) / 2 = 10.005
