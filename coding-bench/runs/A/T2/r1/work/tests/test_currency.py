from decimal import Decimal as D

import pytest

from inventory_service.cli import main
from inventory_service.currency import DECIMALS, RATES, UnsupportedCurrency, convert, currency_code, format_amount
from inventory_service.models import Customer, Order, OrderLine, ValidationError
from inventory_service.orders import OrderService
from inventory_service.pricing import compute_order_total, quote
from inventory_service import storage
from inventory_service.csv_io import export_orders


def test_convert_to_eur():
    assert convert(D("10.00"), "EUR") == D("9.20")


def test_quote_in_eur_keeps_usd_rules(catalog, customers):
    b = quote(catalog, customers["C1"], [("TOO-0001", 2)], currency="EUR")
    assert b.currency == "EUR"
    assert b.subtotal == D("23.00")
    assert b.total == b.taxable + b.tax + b.shipping


def test_convert_rates_and_rounding():
    assert convert(D("10.00"), "EUR") == D("9.20")
    assert convert(D("10.00"), "USD") == D("10.00")
    assert convert(D("10.00"), "GBP") == D("7.90")
    assert convert(D("10.00"), "JPY") == D("1513")
    assert convert(D("12.345"), "JPY") == D("1868")   # 1867.7985, half-up to whole units
    assert convert(D("0"), "JPY") == D("0")


def test_currency_codes_are_case_insensitive_and_padded():
    assert convert(D("1.00"), " eur ") == D("0.92")
    assert convert("2.50", "gbp") == D("1.98")
    assert currency_code("\teUR\n") == "EUR"
    assert RATES["JPY"] == D("151.30") and DECIMALS["JPY"] == 0


def test_unknown_currency():
    with pytest.raises(UnsupportedCurrency):
        convert(D("1.00"), "RUB")
    assert isinstance(UnsupportedCurrency("x"), ValidationError)


def test_format_amount():
    assert format_amount(D("9.2"), "EUR") == "9.20"
    assert format_amount(D("1866.9"), "JPY") == "1867"
    assert format_amount(D("3"), "USD") == "3.00"
    assert format_amount(D("71.10"), " gbp ") == "71.10"
    with pytest.raises(UnsupportedCurrency):
        format_amount(D("1.00"), "CHF")


def test_usd_results_are_unchanged(catalog, customers):
    b = compute_order_total([OrderLine("GAR-0001", 2, D("45.00"))], catalog, customers["C2"])
    assert b.subtotal == D("90.00") and b.line_discounts == D("13.50") and b.tier_discount == D("3.83")
    assert b.taxable == D("72.67") and b.tax == D("6.45") and b.shipping == D("15.99") and b.total == D("95.11")
    assert b.currency == "USD"


def test_gbp_breakdown_converts_every_component(catalog, customers):
    b = quote(catalog, customers["C2"], [("GAR-0001", 2)], currency="GBP")
    assert b.currency == "GBP"
    assert b.subtotal == D("71.10")
    assert b.line_discounts == D("10.67")            # 13.50 x 0.79 = 10.665
    assert b.tier_discount == D("3.03")              # 3.83 x 0.79
    assert b.tax == D("5.10")                        # 6.45 x 0.79 = 5.0955
    assert b.shipping == D("12.63")                  # 15.99 x 0.79
    assert b.taxable == D("57.40")                   # from the converted amounts
    assert b.total == b.taxable + b.tax + b.shipping


def test_converted_lines(catalog, customers):
    b = quote(catalog, customers["C2"], [("GAR-0001", 2)], currency=" eur ")
    line = b.lines[0]
    assert line["gross"] == D("82.80") and line["discount"] == D("12.42")
    assert line["net"] == line["gross"] - line["discount"]
    assert line["percent"] == D("15")                # the rule itself stays USD
    assert line["quantity"] == 2


def test_to_dict_keys_unchanged(catalog, customers):
    b = quote(catalog, customers["C1"], [("TOO-0001", 2)], currency="EUR")
    assert list(b.to_dict()) == ["subtotal", "line_discounts", "tier_discount", "coupon_discount", "taxable",
                                 "tax", "shipping", "total"]
    assert b.to_dict()["total"] == D("33.86")


def test_coupon_and_shipping_rules_stay_usd(catalog, customers):
    # FLAT5 needs 20 USD and gives 5 USD, though 6.50 USD is 983 JPY
    with pytest.raises(ValidationError):
        quote(catalog, customers["C1"], [("KIT-0001", 1)], coupon="FLAT5", currency="JPY")
    b = quote(catalog, customers["C1"], [("TOO-0002", 2)], coupon="FLAT5", currency="JPY")
    assert b.coupon_discount == D("757")             # 5 USD x 151.30
    # BIG25 caps the discount at 100 USD, not 100 JPY
    b = quote(catalog, customers["C1"], [("TOO-0002", 10)], coupon="BIG25", currency="JPY")
    assert b.coupon_discount == D("15130")
    # free shipping starts at 100 USD taxable, even when that is under 100 EUR
    b = quote(catalog, customers["C1"], [("TOO-0001", 8)], currency="EUR")
    assert b.shipping == D("0.00") and b.total == D("98.67")


def test_order_keeps_its_currency(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="eur ")
    assert o.currency == "EUR"
    assert o.totals["subtotal"] == D("23.00") and o.totals["total"] == D("33.86")
    usd = svc.create_order("C1", [("TOO-0001", 2)])
    assert usd.currency == "USD" and usd.totals["total"] == D("36.80")


def test_refunds_stay_usd_only(svc):
    o = svc.create_order("C3", [("GAR-0001", 1)], currency="GBP")
    svc.ship(o.id)
    with pytest.raises(ValidationError):
        svc.refund(o.id, {"GAR-0001": 1})


def test_order_currency_round_trips(svc, catalog, inventory):
    o = svc.create_order("C4", [("LIT-0001", 1)], coupon="FLAT5", currency="JPY")
    assert o.to_dict()["currency"] == "JPY"
    s = storage.State(catalog, inventory, svc)
    data = storage.to_dict(s)
    assert data["orders"][0]["currency"] == "JPY"
    assert storage.from_dict(data).orders.get(o.id).currency == "JPY"


def test_state_file_without_currency_is_usd(tmp_path):
    p = tmp_path / "old.json"
    p.write_text('{"version": 2, "catalog": [], "inventory": {}, "customers": [{"id": "C1", "name": "Ann"}], '
                 '"orders": [{"id": "O1001", "customer_id": "C1", "lines": [], "region": "US-CA", "coupon": null, '
                 '"status": "reserved", "totals": {}, "refunds": []}], "next_order": 1002, "next_refund": 1}')
    s = storage.load(str(p))
    assert s.orders.get("O1001").currency == "USD"
    assert Order("O1", "C1", [], "US-CA").currency == "USD"


def test_export_orders_gains_a_currency_column(svc):
    rows = export_orders(svc.orders.values()).splitlines()
    assert rows[0].endswith(",currency")
    o_usd = svc.create_order("C2", [("GAR-0001", 2)], coupon="SAVE10")
    o_jpy = svc.create_order("C2", [("GAR-0001", 2)], coupon="SAVE10", currency="JPY")
    rows = export_orders([o_usd, o_jpy]).splitlines()
    assert rows[1] == "O1001,C2,reserved,GAR-0001 x 2,90.00,24.60,5.80,15.99,87.19,0.00,USD"
    assert rows[2] == "O1002,C2,reserved,GAR-0001 x 2,13617,3722,878,2419,13192,0,JPY"


def test_cli_prints_the_currency(tmp_path, capsys):
    st = str(tmp_path / "state.json")
    prod = tmp_path / "p.csv"
    prod.write_text("sku,name,price,category\nTOO-0001,Hammer,12.50,tools\n")
    stock = tmp_path / "s.csv"
    stock.write_text("sku,quantity\nTOO-0001,10\n")
    assert main(["--state", st, "import-products", str(prod)]) == 0
    assert main(["--state", st, "import-stock", str(stock)]) == 0
    assert main(["--state", st, "add-customer", "C9", "Zoe"]) == 0
    assert main(["--state", st, "order", "C9", "TOO-0001:2", "--currency", "EUR"]) == 0
    assert "order O1001 reserved, total 29.26 EUR" in capsys.readouterr().out
    assert main(["--state", st, "quote", "C9", "TOO-0001:2", "--currency", "GBP"]) == 0
    out = capsys.readouterr().out
    assert "total: 25.12 GBP" in out and "shipping: 3.94 GBP" in out
    assert main(["--state", st, "order", "C9", "TOO-0001:2", "--currency", "RUB"]) == 2
