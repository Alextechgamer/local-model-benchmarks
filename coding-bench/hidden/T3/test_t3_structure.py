"""Task 3: the structure rule from the README, and the public API that must survive the refactor."""
import ast
import inspect
import pathlib


def _pricing_source():
    import inventory_service.pricing as pricing
    return pathlib.Path(pricing.__file__).read_text(encoding="utf-8")


def test_task_no_function_longer_than_40_lines():
    tree = ast.parse(_pricing_source())
    long = [(n.name, n.end_lineno - n.lineno + 1) for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.end_lineno - n.lineno + 1 > 40]
    assert long == [], f"functions longer than 40 lines: {long}"


def test_keep_public_api():
    import dataclasses

    from inventory_service import pricing
    for name in ("TIER_DISCOUNTS", "BULK_THRESHOLD", "BULK_PERCENT", "CATEGORY_PROMOS", "COUPONS", "TAX_RATES",
                 "FREE_SHIPPING_FROM", "PriceBreakdown", "shipping_cost", "compute_order_total", "quote"):
        assert hasattr(pricing, name), name
    assert list(inspect.signature(pricing.compute_order_total).parameters) == [
        "lines", "catalog", "customer", "coupon", "region"]
    assert list(inspect.signature(pricing.quote).parameters) == ["catalog", "customer", "items", "coupon"]
    assert list(inspect.signature(pricing.shipping_cost).parameters) == ["weight_kg", "discounted_subtotal"]
    assert [f.name for f in dataclasses.fields(pricing.PriceBreakdown)] == [
        "subtotal", "line_discounts", "tier_discount", "coupon_discount", "taxable", "tax", "shipping", "total", "lines"]


def test_keep_shipping_cost_table():
    from decimal import Decimal as D

    from inventory_service.pricing import shipping_cost
    cases = [("0", "0", "4.99"), ("1", "99.99", "4.99"), ("1.01", "0", "9.99"), ("5", "0", "9.99"),
             ("5.01", "0", "11.49"), ("7", "0", "12.99"), ("7.2", "0", "14.49"), ("40", "100", "0")]
    for w, sub, want in cases:
        assert shipping_cost(w, sub) == D(want), (w, sub)
