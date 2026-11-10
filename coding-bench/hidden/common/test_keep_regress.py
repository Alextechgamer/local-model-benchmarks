"""Regression tests run for every task. They pass on every task's starting code and every reference solution.

They stay away from the planted bugs (bulk discount at exactly 10 units, cancelling multi-line orders, empty weight
cells, refunds of orders with tier or coupon discounts).
"""
import json
from decimal import Decimal as D

import pytest

from _hx import customer, lines, world


def test_keep_money_helpers():
    from inventory_service.money import allocate_proportionally, round_money, split_evenly
    assert round_money("0.125") == D("0.13")
    assert round_money("7.5", 0) == D("8")
    assert split_evenly("0.05", 2) == [D("0.03"), D("0.02")]
    assert allocate_proportionally("0.10", [1, 2]) == [D("0.03"), D("0.07")]


def test_keep_catalog_rules():
    from inventory_service.models import ValidationError
    cat, *_ = world()
    with pytest.raises(ValidationError):
        cat.add_product("ABC-12345", "x", "1", "misc")
    with pytest.raises(ValidationError):
        cat.add_product("ABC-1234", "x", "-1", "misc")
    p = cat.add_product(" abc-1234 ", " Thing ", "2.50", " Misc  Stuff ")
    assert (p.sku, p.name, p.category) == ("ABC-1234", "Thing", "misc stuff")
    cat.deactivate("ABC-1234")
    assert cat.search(text="thing") == []


@pytest.mark.parametrize("cid,items,coupon,total", [
    ("C1", [("TOO-0001", 1)], None, "18.40"),             # 12.50 + 0.91 tax + 4.99
    ("C4", [("TOO-0002", 2)], None, "178.00"),            # Oregon, free shipping
    ("C3", [("LIT-0001", 3)], None, "104.58"),            # 8% lighting, gold 10%, DE 19%, 3.3 kg
    ("C2", [("KIT-0002", 2), ("TOO-0001", 1)], "FLAT5", "100.01"),
    ("C5", [("TOO-0002", 3)], "BIG25", "193.29"),
    ("C1", [("KIT-0001", 11)], None, "82.83"),            # bulk above the threshold
])
def test_keep_pricing_totals(cid, items, coupon, total):
    from inventory_service.pricing import compute_order_total
    cat, *_ = world()
    b = compute_order_total(lines(cat, *items), cat, customer(cid), coupon)
    assert b.total == D(total)
    assert b.total == b.taxable + b.tax + b.shipping


def test_keep_pricing_errors():
    from inventory_service.models import ValidationError
    from inventory_service.pricing import compute_order_total
    cat, *_ = world()
    with pytest.raises(ValidationError):
        compute_order_total([], cat, customer("C1"))
    with pytest.raises(ValidationError):
        compute_order_total(lines(cat, ("KIT-0001", 2)), cat, customer("C1"), "BIG25")


def test_keep_reserve_commit_single_line():
    from inventory_service.inventory import InsufficientStock
    cat, inv, svc, clock = world(stock=10)
    o = svc.create_order("C1", [("KIT-0002", 4)])
    assert inv.available("KIT-0002") == 6
    with pytest.raises(InsufficientStock):
        svc.create_order("C1", [("KIT-0002", 7)])
    svc.ship(o.id)
    assert (inv.on_hand("KIT-0002"), inv.available("KIT-0002")) == (6, 6)
    o2 = svc.create_order("C4", [("KIT-0002", 2)])
    svc.cancel(o2.id)
    assert inv.available("KIT-0002") == 6


def test_keep_expiry_and_low_stock():
    cat, inv, svc, clock = world(stock=5)
    svc.create_order("C1", [("TOO-0001", 2)])
    clock.t += 500
    svc.create_order("C1", [("GAR-0002", 1)])
    clock.t += 200
    assert inv.expire_reservations(600) == ["O1001"]
    assert ("GAR-0002", 4) in inv.low_stock(4)
    assert ("TOO-0001", 5) not in inv.low_stock(4)


def test_keep_refund_without_order_discounts():
    cat, inv, svc, _ = world()
    o = svc.create_order("C1", [("TOO-0001", 4)])            # 50.00 + 3.63 tax + 9.99 shipping (3.2 kg)
    svc.ship(o.id)
    r = svc.refund(o.id, {"TOO-0001": 2})
    assert r.amount == D("26.81")                           # 25.00 + 1.81 tax
    r2 = svc.refund(o.id, {"TOO-0001": 2}, restock=False)
    assert r.amount + r2.amount == o.totals["total"]
    assert inv.on_hand("TOO-0001") == 48 and o.status == "refunded"


def test_keep_csv_import_with_weights():
    from inventory_service.catalog import Catalog
    from inventory_service.csv_io import import_products
    c = Catalog()
    r = import_products("category,price,name,sku,weight_kg\nTools,3.00,Nail box,too-0009,0.5\n\n"
                        "Tools,abc,Bad,TOO-0010,1\n", c)
    assert (r.added, [n for n, _ in r.errors]) == (1, [4])
    assert c.get("TOO-0009").weight_kg == D("0.5")
    r = import_products("sku,name,price,category,weight_kg\nTOO-0009,Nail box,3.50,tools,0.5\n", c)
    assert r.updated == 1 and c.get("TOO-0009").price == D("3.50")


def test_keep_export_and_storage(tmp_path):
    from inventory_service import storage
    from inventory_service.csv_io import export_orders
    cat, inv, svc, _ = world()
    o = svc.create_order("C4", [("TOO-0002", 1)])
    row = export_orders(svc.orders.values()).splitlines()[1].split(",")
    assert row[:9] == [o.id, "C4", "reserved", "TOO-0002 x 1", "89.00", "0.00", "0.00", "9.99", "98.99"]
    p = str(tmp_path / "st.json")
    storage.save(storage.State(cat, inv, svc), p)
    data = json.loads(open(p, encoding="utf-8").read())
    assert data["version"] == 2
    s = storage.load(p)
    assert s.orders.get(o.id).totals["total"] == D("98.99")
    assert s.inventory.reserved("TOO-0002") == 1


def test_keep_cli_quote_and_report(tmp_path, capsys):
    from inventory_service.cli import main
    st = str(tmp_path / "s.json")
    p = tmp_path / "p.csv"
    p.write_text("sku,name,price,category,weight_kg\nTOO-0002,Drill,89.00,tools,1.9\n")
    s = tmp_path / "s.csv"
    s.write_text("sku,quantity\nTOO-0002,3\n")
    assert main(["--state", st, "import-products", str(p)]) == 0
    assert main(["--state", st, "import-stock", str(s)]) == 0
    assert main(["--state", st, "add-customer", "Z1", "Zed", "--region", "US-OR"]) == 0
    capsys.readouterr()
    assert main(["--state", st, "quote", "Z1", "TOO-0002:2"]) == 0
    assert "total: 178.00" in capsys.readouterr().out
    assert main(["--state", st, "order", "Z1", "TOO-0002:1"]) == 0
    assert main(["--state", st, "ship", "O1001"]) == 0
    capsys.readouterr()
    assert main(["--state", st, "report", "valuation"]) == 0
    assert capsys.readouterr().out.strip() == "178.00"
