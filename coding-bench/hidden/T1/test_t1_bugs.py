"""Task 1: the three planted bugs, with inputs other than the visible tests'. test_task_* fail on the starting code."""
from decimal import Decimal as D

import pytest

from _hx import customer, lines, world


# bug 1: the bulk discount starts at exactly BULK_THRESHOLD units
def test_task_bulk_at_threshold_kettles_silver():
    from inventory_service.pricing import compute_order_total
    cat, *_ = world()
    b = compute_order_total(lines(cat, ("KIT-0002", 10)), cat, customer("C2"))
    assert b.line_discounts == D("19.95")          # 5% of 399.00
    assert b.tier_discount == D("18.95")           # 5% of 379.05 = 18.9525


def test_task_bulk_at_threshold_through_order_service():
    cat, inv, svc, _ = world()
    o = svc.create_order("C4", [("TOO-0001", 6), ("TOO-0001", 4)])     # merged to 10
    assert o.totals["line_discounts"] == D("6.25")
    assert o.totals["total"] == D("118.75")        # Oregon: no tax; 118.75 is over the free-shipping line


def test_keep_bulk_below_and_above_threshold():
    from inventory_service.pricing import compute_order_total
    cat, *_ = world()
    assert compute_order_total(lines(cat, ("KIT-0002", 9)), cat, customer("C1")).line_discounts == D("0")
    assert compute_order_total(lines(cat, ("KIT-0002", 11)), cat, customer("C1")).line_discounts == D("21.95")


# bug 2: releasing an order frees all of its reservations
def test_task_cancel_three_line_order_frees_everything():
    cat, inv, svc, _ = world(stock=20)
    o = svc.create_order("C1", [("TOO-0001", 3), ("LIT-0001", 4), ("KIT-0001", 5)])
    svc.cancel(o.id)
    assert [inv.available(s) for s in ("TOO-0001", "LIT-0001", "KIT-0001")] == [20, 20, 20]
    assert inv.reservations_for(o.id) == []


def test_task_release_returns_all_units():
    _, inv, _, _ = world()
    inv.reserve("X1", "TOO-0001", 2)
    inv.reserve("X1", "TOO-0002", 3)
    inv.reserve("X2", "TOO-0001", 4)
    assert inv.release("X1") == 5
    assert inv.reserved("TOO-0001") == 4


def test_task_failed_order_rolls_back_earlier_lines():
    from inventory_service.inventory import InsufficientStock
    cat, inv, svc, _ = world(stock=10)
    with pytest.raises(InsufficientStock):
        svc.create_order("C1", [("TOO-0001", 2), ("GAR-0001", 3), ("LIT-0001", 11)])
    assert inv.available("TOO-0001") == 10 and inv.available("GAR-0001") == 10


def test_keep_release_single_line():
    _, inv, _, _ = world()
    inv.reserve("X1", "TOO-0001", 2)
    assert inv.release("X1") == 2 and inv.release("X1") == 0


# bug 3: an empty or blank weight_kg cell means the default weight 0
def test_task_blank_weight_cells_use_default():
    from inventory_service.catalog import Catalog
    from inventory_service.csv_io import import_products
    c = Catalog()
    text = ("sku,name,price,category,weight_kg\nAAA-0001,One,1.00,misc,\nAAA-0002,Two,2.00,misc,   \n"
            "AAA-0003,Three,3.00,misc,1.5\n")
    r = import_products(text, c)
    assert r.ok and r.added == 3
    assert [c.get(s).weight_kg for s in ("AAA-0001", "AAA-0002", "AAA-0003")] == [D("0"), D("0"), D("1.5")]


def test_task_blank_weight_on_update():
    from inventory_service.csv_io import import_products
    cat, *_ = world()
    r = import_products("sku,name,price,category,weight_kg\nGAR-0002,Hose 25m,29.99,garden,\n", cat)
    assert r.updated == 1 and r.ok
    assert cat.get("GAR-0002").weight_kg == D("0")


def test_keep_missing_weight_column_and_short_rows():
    from inventory_service.catalog import Catalog
    from inventory_service.csv_io import import_products
    c = Catalog()
    r = import_products("sku,name,price,category\nAAA-0001,One,1.00,misc\n", c)
    assert r.ok and c.get("AAA-0001").weight_kg == D("0")
