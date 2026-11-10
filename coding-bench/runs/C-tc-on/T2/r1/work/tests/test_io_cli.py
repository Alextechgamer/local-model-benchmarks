import json
from decimal import Decimal as D

from inventory_service import storage
from inventory_service.catalog import Catalog
from inventory_service.cli import main
from inventory_service.csv_io import export_orders, import_products, import_stock
from inventory_service.inventory import Inventory


def test_import_products_reports_bad_rows():
    text = "SKU,Name,Price,Category,Weight_kg\nTOO-0001,Hammer,12.50,Tools,0.8\nbad,Thing,1,x,1\nTOO-0002,Drill,abc,tools,1\n"
    c = Catalog()
    r = import_products(text, c)
    assert (r.added, r.updated) == (1, 0)
    assert [n for n, _ in r.errors] == [3, 4]


def test_import_products_weight_is_optional():
    c = Catalog()
    r = import_products("sku,name,price,category,weight_kg\nKIT-0001,Mug,6.50,kitchen,\n", c)
    assert r.ok and c.get("KIT-0001").weight_kg == D("0")


def test_import_stock_set_and_add(catalog):
    inv = Inventory()
    r = import_stock("sku,quantity\nTOO-0001,5\nZZZ-9999,3\nTOO-0002,x\n", inv, catalog)
    assert r.updated == 1 and len(r.errors) == 2
    import_stock("sku,quantity\nTOO-0001,5\n", inv, catalog, mode="add")
    assert inv.on_hand("TOO-0001") == 10


def test_export_orders(svc):
    o = svc.create_order("C2", [("GAR-0001", 2)], coupon="SAVE10")
    rows = export_orders(svc.orders.values()).splitlines()
    assert rows[0].startswith("order_id,customer_id,status")
    assert rows[1].startswith(f"{o.id},C2,reserved,GAR-0001 x 2,90.00,")


def test_storage_round_trip(tmp_path, svc, catalog, inventory):
    o = svc.create_order("C1", [("TOO-0001", 2)])
    path = str(tmp_path / "s.json")
    storage.save(storage.State(catalog, inventory, svc), path)
    s = storage.load(path)
    assert s.orders.get(o.id).totals == o.totals
    assert s.inventory.available("TOO-0001") == 48


def test_storage_migrates_version_1(tmp_path):
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"version": 1, "catalog": [{"sku": "TOO-0001", "name": "Hammer", "price_cents": 1250,
                                                       "category": "tools"}],
                             "customers": [{"id": "C1", "name": "Ann"}]}))
    s = storage.load(str(p))
    assert s.catalog.get("TOO-0001").price == D("12.50")
    assert s.orders.customers["C1"].region == "US-CA"


def test_cli_flow(tmp_path, capsys):
    st = str(tmp_path / "state.json")
    prod = tmp_path / "p.csv"
    prod.write_text("sku,name,price,category\nTOO-0001,Hammer,12.50,tools\n")
    stock = tmp_path / "s.csv"
    stock.write_text("sku,quantity\nTOO-0001,10\n")
    assert main(["--state", st, "import-products", str(prod)]) == 0
    assert main(["--state", st, "import-stock", str(stock)]) == 0
    assert main(["--state", st, "add-customer", "C9", "Zoe"]) == 0
    assert main(["--state", st, "order", "C9", "TOO-0001:2"]) == 0
    assert "total 31.80" in capsys.readouterr().out     # no weight column: 0 kg ships at 4.99
    assert main(["--state", st, "order", "C9", "TOO-0001:99"]) == 2
