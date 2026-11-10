import json
from decimal import Decimal as D

import pytest

from inventory_service import storage
from inventory_service.currency import (DECIMALS, RATES, UnsupportedCurrency, convert, format_amount)
from inventory_service.models import ValidationError
from inventory_service.pricing import quote


def test_convert_to_eur():
    from inventory_service.currency import convert
    assert convert(D("10.00"), "EUR") == D("9.20")


def test_quote_in_eur_keeps_usd_rules(catalog, customers):
    from inventory_service.pricing import quote
    b = quote(catalog, customers["C1"], [("TOO-0001", 2)], currency="EUR")
    assert b.currency == "EUR"
    assert b.subtotal == D("23.00")
    assert b.total == b.taxable + b.tax + b.shipping


def test_rates_and_decimals_tables():
    assert RATES == {"USD": D("1"), "EUR": D("0.92"), "GBP": D("0.79"), "JPY": D("151.30")}
    assert DECIMALS == {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


def test_convert_in_all_currencies():
    assert convert(D("10"), "USD") == D("10.00")
    assert convert(D("10.00"), "EUR") == D("9.20")
    assert convert(D("10.00"), "GBP") == D("7.90")
    assert convert(D("10.00"), "JPY") == D("1513")


def test_convert_rounds_half_up_to_the_currency_decimals():
    assert convert(D("12.345"), "JPY") == D("1868")     # 1867.7985 -> 1868
    assert convert(D("0.004"), "JPY") == D("1")         # 0.6052 -> 1
    assert convert(D("0.001"), "JPY") == D("0")         # 0.1513 -> 0
    assert convert(D("1.85"), "EUR") == D("1.70")       # 1.7020 -> 1.70


def test_convert_currency_code_is_case_insensitive_and_stripped():
    assert convert(D("10"), "eur") == D("9.20")
    assert convert(D("10"), " eur ") == D("9.20")
    assert convert(D("10"), "JPY") == D("1513")


def test_convert_unknown_currency_raises():
    with pytest.raises(UnsupportedCurrency):
        convert(D("1"), "CHF")
    assert issubclass(UnsupportedCurrency, ValidationError)


def test_format_amount_uses_the_currency_decimals():
    assert format_amount(D("9.20"), "EUR") == "9.20"
    assert format_amount(D("1867"), "JPY") == "1867"
    assert format_amount(D("1867.4"), "JPY") == "1867"
    assert format_amount(D("1513.5"), "JPY") == "1514"
    assert format_amount(D("10"), "USD") == "10.00"
    assert format_amount(D("7.90"), "GBP") == "7.90"
    assert format_amount(D("0"), "JPY") == "0"
    assert format_amount(D("9.20"), " eur ") == "9.20"


def test_format_amount_unknown_currency_raises():
    with pytest.raises(UnsupportedCurrency):
        format_amount(D("1"), "CHF")


def test_quote_in_jpy(catalog, customers):
    b = quote(catalog, customers["C1"], [("TOO-0001", 2)], currency="JPY")
    assert b.currency == "JPY"
    assert b.subtotal == D("3783")       # 25.00 x 151.30 = 3782.50 -> 3783
    assert b.taxable == D("3783")
    assert b.tax == D("274")             # 1.81 x 151.30 = 273.853
    assert b.shipping == D("1511")       # 9.99 x 151.30 = 1511.487
    assert b.total == D("5568")
    assert b.total == b.taxable + b.tax + b.shipping


def test_quote_in_eur_converts_every_field(catalog, customers):
    b = quote(catalog, customers["C2"], [("GAR-0001", 2)], currency="EUR")
    # USD: subtotal 90.00, line discount 13.50, tier 3.83, tax 6.45, shipping 15.99
    assert b.currency == "EUR"
    assert b.subtotal == D("82.80")
    assert b.line_discounts == D("12.42")
    assert b.tier_discount == D("3.52")
    assert b.coupon_discount == D("0.00")
    assert b.taxable == D("66.86")
    assert b.tax == D("5.93")
    assert b.shipping == D("14.71")
    assert b.total == D("87.50")
    assert b.total == b.taxable + b.tax + b.shipping


def test_quote_lines_converted_with_net_from_converted_parts(catalog, customers):
    b = quote(catalog, customers["C2"], [("GAR-0001", 2)], currency="EUR")
    (line,) = b.lines
    assert line["sku"] == "GAR-0001" and line["quantity"] == 2
    assert line["gross"] == D("82.80")       # 90.00 -> EUR
    assert line["discount"] == D("12.42")    # 13.50 -> EUR
    assert line["net"] == D("70.38")
    assert line["net"] == line["gross"] - line["discount"]
    assert line["percent"] == D("15")        # the percent stays a percent


def test_coupon_rules_stay_in_usd(catalog, customers):
    # 203.00 USD is above the BIG25 minimum (200) although 186.76 EUR would be below it
    b = quote(catalog, customers["C1"], [("TOO-0002", 2), ("TOO-0001", 2)], coupon="BIG25", currency="EUR")
    assert b.coupon_discount == D("46.69")   # 25% of 203.00 = 50.75 USD -> EUR
    assert b.total == b.taxable + b.tax + b.shipping
    with pytest.raises(ValidationError):
        quote(catalog, customers["C1"], [("KIT-0001", 1)], coupon="SAVE10", currency="EUR")
    with pytest.raises(ValidationError):
        quote(catalog, customers["C1"], [("TOO-0002", 2), ("TOO-0001", 2)], coupon="NOPE", currency="EUR")


def test_free_shipping_threshold_is_a_usd_amount(catalog, customers):
    # 152.25 USD after the coupon is above FREE_SHIPPING_FROM, so shipping is 0 in any currency
    b = quote(catalog, customers["C1"], [("TOO-0002", 2), ("TOO-0001", 2)], coupon="BIG25", currency="JPY")
    assert b.shipping == D("0")
    assert b.total == b.taxable + b.tax


def test_quote_unknown_currency_raises(catalog, customers):
    with pytest.raises(UnsupportedCurrency):
        quote(catalog, customers["C1"], [("TOO-0001", 1)], currency="CHF")


def test_usd_breakdown_is_unchanged(catalog, customers):
    b_usd = quote(catalog, customers["C1"], [("TOO-0001", 2)])
    assert b_usd.currency == "USD"
    assert b_usd.subtotal == D("25.00") and b_usd.tax == D("1.81") and b_usd.shipping == D("9.99")
    assert b_usd.total == D("36.80")
    assert b_usd.lines[0]["gross"] == D("25.00") and b_usd.lines[0]["net"] == D("25.00")


def test_price_breakdown_to_dict_keeps_its_keys():
    from inventory_service.pricing import PriceBreakdown
    pb = PriceBreakdown(D("1"), D("0"), D("0"), D("0"), D("1"), D("0"), D("0"), D("1"), currency="EUR")
    assert list(pb.to_dict()) == ["subtotal", "line_discounts", "tier_discount", "coupon_discount",
                                  "taxable", "tax", "shipping", "total"]
    assert pb.currency == "EUR"
    assert PriceBreakdown(D("1"), D("0"), D("0"), D("0"), D("1"), D("0"), D("0"), D("1")).currency == "USD"


# --- orders ---------------------------------------------------------------

def test_create_order_keeps_currency_and_converted_totals(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="EUR")
    assert o.currency == "EUR"
    assert o.totals["subtotal"] == D("23.00")
    assert o.totals["total"] == D("33.86")


def test_create_order_jpy(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="JPY")
    assert o.currency == "JPY"
    assert o.totals["total"] == D("5568")


def test_create_order_defaults_to_usd_and_is_unchanged(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)])
    assert o.currency == "USD"
    assert o.totals["total"] == D("36.80")


def test_create_order_with_case_and_spaces_in_currency(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)], currency=" eUr ")
    assert o.currency == "EUR"


def test_create_order_unknown_currency_reserves_nothing(svc, inventory):
    with pytest.raises(UnsupportedCurrency):
        svc.create_order("C1", [("TOO-0001", 2)], currency="CHF")
    assert svc.orders == {}
    assert inventory.available("TOO-0001") == 50


def test_order_currency_round_trips_through_state(tmp_path, svc, catalog, inventory):
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="EUR")
    path = str(tmp_path / "s.json")
    storage.save(storage.State(catalog, inventory, svc), path)
    s = storage.load(path)
    assert s.orders.get(o.id).currency == "EUR"
    assert s.orders.get(o.id).totals == o.totals


def test_state_file_without_currency_loads_as_usd(tmp_path, svc, catalog, inventory):
    o = svc.create_order("C1", [("TOO-0001", 2)])
    path = str(tmp_path / "s.json")
    storage.save(storage.State(catalog, inventory, svc), path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for od in data["orders"]:
        od.pop("currency", None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    s = storage.load(path)
    assert s.orders.get(o.id).currency == "USD"
    assert s.orders.get(o.id).totals["total"] == D("36.80")


def test_order_to_dict_and_from_dict_carry_currency():
    from inventory_service.models import Order, OrderLine
    o = Order("O1", "C1", [OrderLine("TOO-0001", 2, D("12.50"))], "US-CA", currency="GBP")
    d = o.to_dict()
    assert d["currency"] == "GBP"
    assert Order.from_dict(d).currency == "GBP"
    d.pop("currency")
    assert Order.from_dict(d).currency == "USD"


def test_refund_rejects_non_usd_orders(svc):
    o = svc.create_order("C1", [("TOO-0001", 2)], currency="EUR")
    svc.ship(o.id)
    with pytest.raises(ValidationError):
        svc.refund(o.id, {"TOO-0001": 1})
    assert o.refunds == []


def test_refund_still_works_for_usd_orders(svc):
    o = svc.create_order("C4", [("TOO-0002", 2)])
    svc.ship(o.id)
    r = svc.refund(o.id, {"TOO-0002": 1})
    assert r.amount == D("89.00")


# --- CLI --------------------------------------------------------------------

def cli_setup(tmp_path):
    st = str(tmp_path / "state.json")
    prod = tmp_path / "p.csv"
    prod.write_text("sku,name,price,category\nTOO-0001,Hammer,12.50,tools\n")
    stock = tmp_path / "s.csv"
    stock.write_text("sku,quantity\nTOO-0001,10\n")
    from inventory_service.cli import main
    assert main(["--state", st, "import-products", str(prod)]) == 0
    assert main(["--state", st, "import-stock", str(stock)]) == 0
    assert main(["--state", st, "add-customer", "C9", "Zoe"]) == 0
    return st


def test_cli_quote_in_eur(tmp_path, capsys):
    from inventory_service.cli import main
    st = cli_setup(tmp_path)
    assert main(["--state", st, "quote", "C9", "TOO-0001:2", "--currency", "EUR"]) == 0
    out = capsys.readouterr().out
    assert "subtotal: 23.00 EUR" in out
    assert "line_discounts: 0.00 EUR" in out
    assert "tax: 1.67 EUR" in out
    assert "shipping: 4.59 EUR" in out
    assert "total: 29.26 EUR" in out


def test_cli_quote_currency_is_case_insensitive(tmp_path, capsys):
    from inventory_service.cli import main
    st = cli_setup(tmp_path)
    assert main(["--state", st, "quote", "C9", "TOO-0001:2", "--currency", "eur"]) == 0
    assert "total: 29.26 EUR" in capsys.readouterr().out


def test_cli_quote_usd_output_is_unchanged(tmp_path, capsys):
    from inventory_service.cli import main
    st = cli_setup(tmp_path)
    assert main(["--state", st, "quote", "C9", "TOO-0001:2"]) == 0
    out = capsys.readouterr().out
    assert "subtotal: 25.00" in out and "subtotal: 25.00 " not in out
    assert "total: 31.80" in out


def test_cli_order_in_jpy(tmp_path, capsys):
    from inventory_service.cli import main
    st = cli_setup(tmp_path)
    assert main(["--state", st, "order", "C9", "TOO-0001:2", "--currency", "JPY"]) == 0
    assert "order O1001 reserved, total 4812 JPY" in capsys.readouterr().out


def test_cli_order_usd_output_is_unchanged(tmp_path, capsys):
    from inventory_service.cli import main
    st = cli_setup(tmp_path)
    assert main(["--state", st, "order", "C9", "TOO-0001:2"]) == 0
    assert "order O1001 reserved, total 31.80" in capsys.readouterr().out


def test_cli_unknown_currency_exits_2(tmp_path, capsys):
    from inventory_service.cli import main
    st = cli_setup(tmp_path)
    assert main(["--state", st, "quote", "C9", "TOO-0001:2", "--currency", "CHF"]) == 2
    assert "unsupported currency" in capsys.readouterr().err
    assert main(["--state", st, "order", "C9", "TOO-0001:2", "--currency", "CHF"]) == 2


# --- CSV export ---------------------------------------------------------------

def test_export_orders_has_currency_column_and_per_currency_decimals(svc):
    from inventory_service.csv_io import export_orders
    svc.create_order("C1", [("TOO-0001", 2)])
    svc.create_order("C2", [("GAR-0001", 2)], currency="EUR")
    svc.create_order("C3", [("TOO-0001", 2)], currency="JPY")
    rows = export_orders(svc.orders.values()).splitlines()
    assert rows[0] == ("order_id,customer_id,status,items,subtotal,discount,tax,shipping,total,refunded,currency")
    assert rows[1] == "O1001,C1,reserved,TOO-0001 x 2,25.00,0.00,1.81,9.99,36.80,0.00,USD"
    assert rows[2] == "O1002,C2,reserved,GAR-0001 x 2,82.80,15.94,5.93,14.71,87.50,0.00,EUR"
    assert rows[3] == "O1003,C3,reserved,TOO-0001 x 2,3783,378,648,1511,5564,0,JPY"
