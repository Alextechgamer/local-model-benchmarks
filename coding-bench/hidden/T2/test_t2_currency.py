"""Task 2: multi-currency pricing, as specified in the task README. test_task_* fail on the starting code."""
import json
from decimal import Decimal as D

import pytest

from _hx import customer, lines, world


def test_task_convert_rates_and_rounding():
    from inventory_service.currency import convert
    assert convert(D("10"), "EUR") == D("9.20")
    assert convert("1.005", "USD") == D("1.01")
    assert convert(D("12.34"), "JPY") == D("1867")       # 1867.042
    assert convert(D("0.01"), "GBP") == D("0.01")        # 0.0079
    assert convert(D("5"), "jpy") == D("757")            # 756.5 rounds half-up
    assert convert(D("100"), " gbp ") == D("79.00")


def test_task_unknown_currency():
    from inventory_service.currency import UnsupportedCurrency, convert
    from inventory_service.models import ValidationError
    with pytest.raises(UnsupportedCurrency):
        convert(D("1"), "CHF")
    assert issubclass(UnsupportedCurrency, ValidationError)


def test_task_tables_and_format():
    from inventory_service.currency import DECIMALS, RATES, format_amount
    assert RATES == {"USD": D("1"), "EUR": D("0.92"), "GBP": D("0.79"), "JPY": D("151.30")}
    assert DECIMALS == {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}
    assert format_amount(D("1867"), "JPY") == "1867"
    assert format_amount(D("9.2"), "eur") == "9.20"


def test_task_breakdown_in_eur():
    from inventory_service.pricing import compute_order_total
    cat, *_ = world()
    b = compute_order_total(lines(cat, ("GAR-0001", 2)), cat, customer("C2"), currency="eur")
    assert b.currency == "EUR"
    assert {k: str(v) for k, v in b.to_dict().items()} == {
        "subtotal": "82.80", "line_discounts": "12.42", "tier_discount": "3.52", "coupon_discount": "0.00",
        "taxable": "66.86", "tax": "5.93", "shipping": "14.71", "total": "87.50"}
    assert (b.lines[0]["gross"], b.lines[0]["discount"], b.lines[0]["net"]) == (D("82.80"), D("12.42"), D("70.38"))


def test_task_breakdown_in_jpy_with_fixed_coupon():
    from inventory_service.pricing import compute_order_total
    cat, *_ = world()
    b = compute_order_total(lines(cat, ("KIT-0002", 2), ("TOO-0001", 1)), cat, customer("C6"), "FLAT5",
                            currency="JPY")
    assert {k: str(v) for k, v in b.to_dict().items()} == {
        "subtotal": "13965", "line_discounts": "0", "tier_discount": "699", "coupon_discount": "757",
        "taxable": "12509", "tax": "1251", "shipping": "1511", "total": "15271"}
    assert [(d["gross"], d["net"]) for d in b.lines] == [(D("12074"), D("12074")), (D("1891"), D("1891"))]


def test_task_rules_stay_in_usd():
    from inventory_service.models import ValidationError
    from inventory_service.pricing import compute_order_total
    cat, *_ = world()
    with pytest.raises(ValidationError):           # 45.00 USD is below SAVE10's 50 USD minimum in any currency
        compute_order_total(lines(cat, ("GAR-0001", 1)), cat, customer("C1"), "SAVE10", currency="JPY")
    b = compute_order_total(lines(cat, ("TOO-0002", 1), ("TOO-0001", 1)), cat, customer("C4"), currency="GBP")
    assert b.shipping == D("0.00")                 # 101.50 USD after discounts: free shipping, though 80.19 GBP


def test_task_usd_default_and_currency_field():
    from inventory_service.pricing import compute_order_total, quote
    cat, *_ = world()
    b = compute_order_total(lines(cat, ("GAR-0001", 2)), cat, customer("C2"))
    assert b.currency == "USD" and b.total == D("95.11")
    q = quote(cat, customer("C2"), [("GAR-0001", 2)], currency="USD")
    assert q.to_dict() == b.to_dict()


def test_task_order_in_eur_saved_and_loaded(tmp_path):
    from inventory_service import storage
    cat, inv, svc, _ = world()
    o = svc.create_order("C3", [("LIT-0001", 3)], currency="eur")
    assert o.currency == "EUR"
    assert o.totals["total"] == D("96.21")
    assert inv.available("LIT-0001") == 47
    p = str(tmp_path / "s.json")
    storage.save(storage.State(cat, inv, svc), p)
    assert storage.load(p).orders.get(o.id).currency == "EUR"
    data = json.loads(open(p, encoding="utf-8").read())
    for order in data["orders"]:
        order.pop("currency", None)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    assert storage.load(p).orders.get(o.id).currency == "USD"


def test_task_refund_of_non_usd_order_rejected():
    from inventory_service.models import ValidationError
    cat, inv, svc, _ = world()
    o = svc.create_order("C3", [("LIT-0001", 1)], currency="GBP")
    svc.ship(o.id)
    with pytest.raises(ValidationError):
        svc.refund(o.id, {"LIT-0001": 1})
    usd = svc.create_order("C4", [("TOO-0002", 1)])
    svc.ship(usd.id)
    assert svc.refund(usd.id, {"TOO-0002": 1}).amount == D("98.99")


def _cli_state(tmp_path):
    from inventory_service import storage
    cat, inv, svc, _ = world()
    p = str(tmp_path / "s.json")
    storage.save(storage.State(cat, inv, svc), p)
    return p


def test_task_cli_quote_and_order_in_eur(tmp_path, capsys):
    from inventory_service.cli import main
    st = _cli_state(tmp_path)
    assert main(["--state", st, "quote", "C3", "LIT-0001:3", "--currency", "EUR"]) == 0
    out = capsys.readouterr().out
    assert "total: 96.21 EUR" in out and "tax: 13.89 EUR" in out
    assert main(["--state", st, "order", "C3", "LIT-0001:3", "--currency", "eur"]) == 0
    assert "total 96.21 EUR" in capsys.readouterr().out
    assert main(["--state", st, "quote", "C3", "LIT-0001:3", "--currency", "CHF"]) == 2


def test_task_cli_usd_output_unchanged(tmp_path, capsys):
    from inventory_service.cli import main
    st = _cli_state(tmp_path)
    assert main(["--state", st, "order", "C4", "TOO-0002:2", "--currency", "USD"]) == 0
    assert capsys.readouterr().out.strip() == "order O1001 reserved, total 178.00"


def test_task_export_has_currency_column():
    from inventory_service.csv_io import export_orders
    cat, inv, svc, _ = world()
    svc.create_order("C4", [("TOO-0002", 2)])
    svc.create_order("C6", [("KIT-0002", 2), ("TOO-0001", 1)], "FLAT5", currency="JPY")
    rows = [r.split(",") for r in export_orders(svc.orders.values()).splitlines()]
    assert rows[0][-1] == "currency"
    assert rows[1][-1] == "USD" and rows[1][8] == "178.00"
    assert rows[2][-1] == "JPY"
    assert rows[2][4:10] == ["13965", "1456", "1251", "1511", "15271", "0"]


def test_keep_usd_totals_unchanged():
    from inventory_service.pricing import compute_order_total
    cat, *_ = world()
    b = compute_order_total(lines(cat, ("LIT-0001", 3)), cat, customer("C3"))
    assert b.total == D("104.58")
