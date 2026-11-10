from decimal import Decimal as D

import pytest

from inventory_service.currency import RATES, DECIMALS, convert, format_amount, UnsupportedCurrency
from inventory_service.models import ValidationError
from inventory_service.pricing import compute_order_total, quote
from inventory_service.models import Order, OrderLine


def test_convert_to_eur():
    assert convert(D("10.00"), "EUR") == D("9.20")


def test_convert_rounds_half_up():
    assert convert(D("0.005"), "USD") == D("0.01")      # not banker's rounding
    assert convert(D("0.5"), "JPY") == D("76")          # 75.65 -> 76
    assert convert(D("10.00"), "GBP") == D("7.90")


def test_convert_is_case_insensitive_and_trims():
    assert convert(D("10.00"), " eur ") == D("9.20")
    assert convert(D("10.00"), "jpy") == D("1513")


def test_convert_unknown_currency():
    with pytest.raises(UnsupportedCurrency):
        convert(D("1.00"), "CAD")
    assert issubclass(UnsupportedCurrency, ValidationError)


def test_convert_usd_is_identity():
    assert convert(D("12.34"), "USD") == D("12.34")


def test_format_amount():
    assert format_amount(D("9.2"), "EUR") == "9.20"
    assert format_amount(D("1867.4"), "JPY") == "1867"
    assert format_amount(D("12.3"), "USD") == "12.30"


def test_format_amount_unknown_currency():
    with pytest.raises(UnsupportedCurrency):
        format_amount(D("1"), "CAD")


def test_quote_in_eur_keeps_usd_rules(catalog, customers):
    from inventory_service.pricing import quote
    b = quote(catalog, customers["C1"], [("TOO-0001", 2)], currency="EUR")
    assert b.currency == "EUR"
    assert b.subtotal == D("23.00")
    assert b.total == b.taxable + b.tax + b.shipping


def test_usd_results_unchanged(catalog, customers):
    from inventory_service.pricing import compute_order_total
    from inventory_service.models import OrderLine
    ln = [OrderLine("TOO-0001", 2, D("12.50"))]
    b = compute_order_total(ln, catalog, customers["C1"])
    assert b.currency == "USD"
    assert b.subtotal == D("25.00")
    assert b.tax == D("1.81")
    assert b.shipping == D("9.99")
    assert b.total == D("36.80")


def test_gbp_breakdown_lines(catalog, customers):
    from inventory_service.pricing import compute_order_total
    from inventory_service.models import OrderLine
    ln = [OrderLine("GAR-0001", 2, D("45.00"))]
    b = compute_order_total(ln, catalog, customers["C2"], currency="GBP")
    assert b.currency == "GBP"
    assert b.lines[0]["gross"] == D("71.10")
    assert b.lines[0]["discount"] == D("10.67")
    assert b.lines[0]["net"] == D("60.43")
    assert b.lines[0]["percent"] == D("15")
    assert b.total == D("75.13")


def test_to_dict_keys_unchanged(catalog, customers):
    from inventory_service.pricing import quote
    b = quote(catalog, customers["C1"], [("TOO-0001", 2)], currency="JPY")
    assert set(b.to_dict()) == {"subtotal", "line_discounts", "tier_discount", "coupon_discount",
                                "taxable", "tax", "shipping", "total"}
    assert b.currency == "JPY"


def test_order_keeps_currency(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="EUR")
    assert o.currency == "EUR"
    assert o.totals["total"] == D("33.86")
    assert o.totals["subtotal"] == D("23.00")
    assert o.totals["shipping"] == D("9.19")


def test_default_order_is_usd(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)])
    assert o.currency == "USD"


def test_order_round_trips_currency():
    o = Order("O1", "C1", [OrderLine("TOO-0001", 1, D("12.50"))], "US-CA", None, "reserved", {}, [], "EUR")
    assert Order.from_dict(o.to_dict()).currency == "EUR"


def test_state_without_currency_loads_usd():
    o = Order.from_dict({"id": "O1", "customer_id": "C1", "lines": [], "region": "US-CA"})
    assert o.currency == "USD"


def test_refund_rejects_non_usd(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="EUR")
    svc.ship(o.id)
    with pytest.raises(ValidationError):
        svc.refund(o.id, {"TOO-0001": 1})


def test_cli_order_in_currency(tmp_path, capsys):
    from inventory_service.cli import main
    st = str(tmp_path / "state.json")
    prod = tmp_path / "p.csv"
    prod.write_text("sku,name,price,category\nTOO-0001,Hammer,12.50,tools\n")
    stock = tmp_path / "s.csv"
    stock.write_text("sku,quantity\nTOO-0001,10\n")
    assert main(["--state", st, "import-products", str(prod)]) == 0
    assert main(["--state", st, "import-stock", str(stock)]) == 0
    assert main(["--state", st, "add-customer", "C9", "Zoe"]) == 0
    assert main(["--state", st, "order", "C9", "TOO-0001:2", "--currency", "EUR"]) == 0
    assert "total 29.26 EUR" in capsys.readouterr().out


def test_cli_unknown_currency_exits_2(tmp_path, capsys):
    from inventory_service.cli import main
    st = str(tmp_path / "state.json")
    assert main(["--state", st, "add-customer", "C9", "Zoe"]) == 0
    assert main(["--state", st, "order", "C9", "TOO-0001:1", "--currency", "CAD"]) == 2


def test_cli_quote_in_currency(tmp_path, capsys):
    from inventory_service.cli import main
    st = str(tmp_path / "state.json")
    prod = tmp_path / "p.csv"
    prod.write_text("sku,name,price,category\nTOO-0001,Hammer,12.50,tools\n")
    assert main(["--state", st, "import-products", str(prod)]) == 0
    assert main(["--state", st, "add-customer", "C9", "Zoe"]) == 0
    assert main(["--state", st, "quote", "C9", "TOO-0001:2", "--currency", "EUR"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert "subtotal: 23.00 EUR" in out
    assert "total: 29.26 EUR" in out


def test_export_orders_has_currency_column(svc):
    from inventory_service.csv_io import export_orders
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="EUR")
    row = export_orders(svc.orders.values()).splitlines()[1]
    assert row.endswith(",EUR")
    assert "33.86" in row


def test_export_orders_jpy_has_no_decimal_point(svc):
    from inventory_service.csv_io import export_orders
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="JPY")
    row = export_orders(svc.orders.values()).splitlines()[1]
    assert row.endswith(",JPY")
    assert "3783" in row and "5568" in row
