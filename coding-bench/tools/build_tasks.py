"""Build tasks/, reference/ and the T6 mutants from project/base. Refuses to run once FROZEN.txt exists.

Each task folder = the base project (package, visible tests, pyproject.toml) + that task's changes + README.md.
Each reference folder = the base project + the task's solution.
"""
import pathlib, shutil, sys

B = pathlib.Path(r"E:\strata-tests\coding-bench")
BASE, SOL = B / "project" / "base", B / "project" / "solutions"
if (B / "FROZEN.txt").exists():
    sys.exit("FROZEN.txt exists: the tasks are frozen, not rebuilding")

PYPROJECT = """[project]
name = "inventory-service"
version = "1.4.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
"""
HEADER = """# inventory-service

A small Python library and command line tool for an online shop's back office: the product catalog, stock levels and
reservations, orders, pricing (discounts, coupons, tax, shipping), refunds, CSV import/export and JSON storage.

- Package: `inventory_service/`. The module docstrings explain the rules.
- Tests: `tests/`. Run them with `python -m pytest` from this folder.
- Python 3.14, standard library only (pytest for the tests).

"""
FOOTER = "\nWork autonomously; do not wait for approval.\n"

TASKS = {
    "T1": ("T1-fix-bugs", """## Your task: fix the failing tests

Some tests in `tests/` fail. Find the bugs in the package and fix them so that the whole test suite passes. The tests
are correct: do not change them.
"""),
    "T2": ("T2-multi-currency", """## Your task: multi-currency pricing

Customers outside the US want prices in their own currency. Add it as described here. Everything not mentioned must
keep working exactly as now, and every result in USD must stay exactly as it is.

1. A new module `inventory_service/currency.py` with:
   - `RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("151.30")}`:
     units of the currency per 1 USD.
   - `DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}`.
   - `class UnsupportedCurrency(ValidationError)`, with `ValidationError` from `inventory_service.models`.
   - `convert(amount_usd, currency) -> Decimal`: the amount times the rate, rounded half-up to the currency's number
     of decimals. Currency codes are case-insensitive and may have surrounding spaces (`" eur "` works). An unknown
     code raises `UnsupportedCurrency`.
   - `format_amount(amount, currency) -> str`: the amount with the currency's number of decimals, e.g. `"9.20"` for
     EUR and `"1867"` for JPY.
2. `pricing.compute_order_total(...)` and `pricing.quote(...)` get a keyword argument `currency="USD"`.
   - Every pricing rule still works in USD, unchanged: coupon minimums, the FLAT5 amount, the BIG25 cap, the shipping
     fees and the free-shipping threshold are USD amounts.
   - After the USD calculation, `subtotal`, `line_discounts`, `tier_discount`, `coupon_discount`, `tax` and
     `shipping` are each converted with `convert()`. Then `taxable = subtotal - line_discounts - tier_discount -
     coupon_discount` and `total = taxable + tax + shipping`, both from the converted amounts.
   - In `breakdown.lines`, each line's `gross` and `discount` are converted with `convert()` and
     `net = gross - discount`.
   - `PriceBreakdown` gets a new last field `currency`: the upper-case code, default `"USD"`. `to_dict()` keeps
     exactly its current keys.
   - With `currency="USD"` every result is exactly what it is today.
3. Orders: `OrderService.create_order(customer_id, items, coupon=None, currency="USD")` prices the order in that
   currency and keeps the code in a new `Order.currency` field (default `"USD"`). The field is saved and loaded with
   the state; state files without it load as `"USD"`. Refunding an order whose currency is not USD raises
   `ValidationError` (refunds stay USD-only for now).
4. CLI: `quote` and `order` get `--currency CODE` (default USD). For a currency other than USD, every amount these
   commands print is shown with the currency's decimals followed by a space and the code, e.g.
   `order O1001 reserved, total 96.21 EUR` and `total: 96.21 EUR`. USD output stays exactly as it is now. An unknown
   code exits with status 2 like other errors.
5. `csv_io.export_orders` gets a new last column `currency`. The amount columns of an order use its currency's number
   of decimals (`money_str` style for 2 decimals, no decimal point for JPY).

`tests/test_currency.py` has a few tests to start from. Add tests for the rest.
"""),
    "T3": ("T3-refactor-pricing", """## Your task: refactor `pricing.py`

`compute_order_total` in `inventory_service/pricing.py` does everything in one long function. Refactor the module
into smaller functions.

Rules:
- No function or method in `inventory_service/pricing.py` may be longer than 40 lines, counted from its `def` line to
  its last line, docstring included (with Python's `ast`: `end_lineno - lineno + 1`).
  `tests/test_pricing_structure.py` checks this.
- Behaviour must not change at all: the same results (including `breakdown.lines`) and the same errors, with the same
  exception type and message, for every input.
- Keep the public names and signatures: `TIER_DISCOUNTS`, `BULK_THRESHOLD`, `BULK_PERCENT`, `CATEGORY_PROMOS`,
  `COUPONS`, `TAX_RATES`, `FREE_SHIPPING_FROM`, `PriceBreakdown` (the same fields in the same order),
  `shipping_cost(weight_kg, discounted_subtotal)`, `compute_order_total(lines, catalog, customer, coupon=None,
  region=None)` and `quote(catalog, customer, items, coupon=None)`.
- Do not change other modules or the existing tests.
"""),
    "T4": ("T4-implement-from-docstring", """## Your task: implement `plan_shipments`

`plan_shipments` in `inventory_service/fulfillment.py` only raises `NotImplementedError`. Implement it. Its docstring
is the specification: follow every rule in it. `tests/test_fulfillment.py` has the docstring's examples; add more
tests of your own if you like.
"""),
    "T5": ("T5-bug-report", """## Your task: a bug report from finance

> **Ticket #4471, from the finance team**
>
> Refunds don't add up. Example: order O1001, customer C1 (standard tier, California), 4 x Garden Chair (GAR-0001)
> with the coupon SAVE10. The customer paid $147.68 in total. They returned 2 chairs and we refunded $74.40. Later
> they returned the other 2 and we refunded $73.28. Half of the order should have been $73.84 each time. We only see
> this on orders that had a coupon or a customer-tier discount; orders without discounts look fine.

Find the cause and fix it.
"""),
    "T6": ("T6-write-tests", """## Your task: write tests for `reports.py`

`inventory_service/reports.py` has no tests. Write them in `tests/test_reports.py`.

- Test the behaviour its docstrings describe, so that any change that breaks it makes at least one of your tests
  fail.
- Your tests must pass on the current code. Do not change `reports.py` or any other module.
- You may use the fixtures in `tests/conftest.py`.

Your tests are scored by mutation testing: small deliberate bugs are put into `reports.py` one at a time, and each
one that makes at least one of your tests fail counts.
"""),
}


def patch(path: pathlib.Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    assert n == 1, f"{path.name}: expected the text once, found {n}: {old[:80]!r}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def copy_base(dest: pathlib.Path) -> pathlib.Path:
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("inventory_service", "tests"):
        shutil.copytree(BASE / name, dest / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (dest / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return dest


def pkg(root, name):
    return root / "inventory_service" / name


# ---------- planted changes in the task starting copies ----------
def start_T1(r):
    patch(pkg(r, "pricing.py"), "if line.quantity >= BULK_THRESHOLD else ZERO", "if line.quantity > BULK_THRESHOLD else ZERO")
    patch(pkg(r, "inventory.py"), "            freed += r.quantity\n            del self._reservations[r.id]\n        return freed",
          "            freed += r.quantity\n            del self._reservations[r.id]\n            return freed\n        return freed")
    patch(pkg(r, "csv_io.py"), "            if not row.get(col):", "            if col not in row:")


def start_T2(r):
    (r / "tests" / "test_currency.py").write_text('''from decimal import Decimal as D


def test_convert_to_eur():
    from inventory_service.currency import convert
    assert convert(D("10.00"), "EUR") == D("9.20")


def test_quote_in_eur_keeps_usd_rules(catalog, customers):
    from inventory_service.pricing import quote
    b = quote(catalog, customers["C1"], [("TOO-0001", 2)], currency="EUR")
    assert b.currency == "EUR"
    assert b.subtotal == D("23.00")
    assert b.total == b.taxable + b.tax + b.shipping
''', encoding="utf-8")


def start_T3(r):
    (r / "tests" / "test_pricing_structure.py").write_text('''import ast
import pathlib

import inventory_service.pricing as pricing


def test_no_function_in_pricing_is_longer_than_40_lines():
    tree = ast.parse(pathlib.Path(pricing.__file__).read_text(encoding="utf-8"))
    long = [(n.name, n.end_lineno - n.lineno + 1) for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.end_lineno - n.lineno + 1 > 40]
    assert long == []
''', encoding="utf-8")


def start_T4(r):
    p = pkg(r, "fulfillment.py")
    text = p.read_text(encoding="utf-8")
    cut = text.index("    left = {w: dict(stock.get(w, {})) for w in priority}")
    p.write_text(text[:cut] + "    raise NotImplementedError\n", encoding="utf-8")
    (r / "tests" / "test_fulfillment.py").write_text('''from inventory_service.fulfillment import plan_shipments


def test_one_warehouse_can_ship_the_whole_line():
    assert plan_shipments([("ABC-0001", 3)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["west", "east"]) == {"west": [("ABC-0001", 3)]}


def test_line_is_split_in_priority_order():
    assert plan_shipments([("ABC-0001", 7)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"east": [("ABC-0001", 5)], "west": [("ABC-0001", 2)]}
''', encoding="utf-8")


def start_T5(r):
    patch(pkg(r, "orders.py"), "amount += taxable + round_money(percent_of(taxable, rate))",
          "amount += taxable + round_money(percent_of(net, rate))")


def start_T6(r):
    pass


# ---------- reference solutions ----------
def ref_T2(r):
    shutil.copy(SOL / "T2" / "currency.py", pkg(r, "currency.py"))
    p = pkg(r, "pricing.py")
    patch(p, "from .models import OrderLine, ValidationError\n",
          "from .currency import code_of, convert\nfrom .models import OrderLine, ValidationError\n")
    patch(p, "    lines: list[dict] = field(default_factory=list)\n\n    @property",
          "    lines: list[dict] = field(default_factory=list)\n    currency: str = \"USD\"\n\n    @property")
    patch(p, "                        region: str | None = None) -> PriceBreakdown:\n    \"\"\"Price an order.",
          "                        region: str | None = None, currency: str = \"USD\") -> PriceBreakdown:\n    \"\"\"Price an order.")
    patch(p, """    return PriceBreakdown(subtotal=subtotal, line_discounts=line_discounts, tier_discount=tier_discount,
                          coupon_discount=coupon_discount, taxable=taxable, tax=tax, shipping=shipping,
                          total=total, lines=details)
""", """    usd = PriceBreakdown(subtotal=subtotal, line_discounts=line_discounts, tier_discount=tier_discount,
                         coupon_discount=coupon_discount, taxable=taxable, tax=tax, shipping=shipping,
                         total=total, lines=details)
    return in_currency(usd, currency)


def in_currency(b: PriceBreakdown, currency: str) -> PriceBreakdown:
    \"\"\"The same breakdown in another currency: each amount converted, taxable and total rebuilt from them.\"\"\"
    code = code_of(currency)
    if code == "USD":
        return b
    c = {k: convert(getattr(b, k), code) for k in ("subtotal", "line_discounts", "tier_discount", "coupon_discount",
                                                   "tax", "shipping")}
    taxable = c["subtotal"] - c["line_discounts"] - c["tier_discount"] - c["coupon_discount"]
    lines = []
    for d in b.lines:
        gross, discount = convert(d["gross"], code), convert(d["discount"], code)
        lines.append(dict(d, gross=gross, discount=discount, net=gross - discount))
    return PriceBreakdown(taxable=taxable, total=taxable + c["tax"] + c["shipping"], lines=lines, currency=code, **c)
""")
    patch(p, "def quote(catalog, customer, items: list[tuple[str, int]], coupon: str | None = None) -> PriceBreakdown:",
          "def quote(catalog, customer, items: list[tuple[str, int]], coupon: str | None = None,\n          currency: str = \"USD\") -> PriceBreakdown:")
    patch(p, "    return compute_order_total(lines, catalog, customer, coupon)\n",
          "    return compute_order_total(lines, catalog, customer, coupon, currency=currency)\n")
    m = pkg(r, "models.py")
    patch(m, "    refunds: list[Refund] = field(default_factory=list)\n",
          "    refunds: list[Refund] = field(default_factory=list)\n    currency: str = \"USD\"\n")
    patch(m, "\"refunds\": [r.to_dict() for r in self.refunds]}",
          "\"refunds\": [r.to_dict() for r in self.refunds], \"currency\": self.currency}")
    patch(m, "                   [Refund.from_dict(x) for x in d.get(\"refunds\", [])])",
          "                   [Refund.from_dict(x) for x in d.get(\"refunds\", [])], d.get(\"currency\", \"USD\"))")
    o = pkg(r, "orders.py")
    patch(o, "    def create_order(self, customer_id: str, items: list[tuple[str, int]], coupon: str | None = None) -> Order:",
          "    def create_order(self, customer_id: str, items: list[tuple[str, int]], coupon: str | None = None,\n"
          "                     currency: str = \"USD\") -> Order:")
    patch(o, "        breakdown = compute_order_total(lines, self.catalog, customer, coupon)\n",
          "        breakdown = compute_order_total(lines, self.catalog, customer, coupon, currency=currency)\n")
    patch(o, "                      \"reserved\", breakdown.to_dict())",
          "                      \"reserved\", breakdown.to_dict(), currency=breakdown.currency)")
    patch(o, "            raise ValidationError(f\"order {order_id} is {order.status}; only shipped orders can be refunded\")\n",
          "            raise ValidationError(f\"order {order_id} is {order.status}; only shipped orders can be refunded\")\n"
          "        if order.currency != \"USD\":\n            raise ValidationError(\"refunds are only supported for USD orders\")\n")
    c = pkg(r, "cli.py")
    patch(c, "from .money import money_str\n", "from .currency import format_amount\nfrom .money import money_str\n")
    patch(c, "        p.add_argument(\"--coupon\")\n", "        p.add_argument(\"--coupon\"); p.add_argument(\"--currency\", default=\"USD\")\n")
    patch(c, """        b = quote(state.catalog, customer, parse_items(a.items), a.coupon)
        for k, v in b.to_dict().items():
            print(f"{k}: {money_str(v)}", file=out)""",
          """        b = quote(state.catalog, customer, parse_items(a.items), a.coupon, currency=a.currency)
        for k, v in b.to_dict().items():
            print(f"{k}: {show(v, b.currency)}", file=out)""")
    patch(c, """        o = svc.create_order(a.customer, parse_items(a.items), a.coupon)
        print(f"order {o.id} reserved, total {money_str(o.totals['total'])}", file=out)""",
          """        o = svc.create_order(a.customer, parse_items(a.items), a.coupon, a.currency)
        print(f"order {o.id} reserved, total {show(o.totals['total'], o.currency)}", file=out)""")
    patch(c, "def build_parser() -> argparse.ArgumentParser:",
          "def show(amount, currency: str) -> str:\n    return money_str(amount) if currency == \"USD\" else f\"{format_amount(amount, currency)} {currency}\"\n\n\n"
          "def build_parser() -> argparse.ArgumentParser:")
    x = pkg(r, "csv_io.py")
    patch(x, "from .money import money_str\n", "from .currency import format_amount\nfrom .money import money_str\n")
    patch(x, "                        \"total\", \"refunded\")", "                        \"total\", \"refunded\", \"currency\")")
    patch(x, """        w.writerow([order.id, order.customer_id, order.status, items, money_str(t.get("subtotal", 0)),
                    money_str(discount), money_str(t.get("tax", 0)), money_str(t.get("shipping", 0)),
                    money_str(t.get("total", 0)), money_str(order.refunded_amount())])""",
          """        cur = order.currency
        fmt = money_str if cur == "USD" else (lambda v: format_amount(v, cur))
        w.writerow([order.id, order.customer_id, order.status, items, fmt(t.get("subtotal", 0)),
                    fmt(discount), fmt(t.get("tax", 0)), fmt(t.get("shipping", 0)),
                    fmt(t.get("total", 0)), fmt(order.refunded_amount()), cur])""")
    start_T2(r)                                   # the visible starter tests are part of the reference too
    (r / "tests" / "test_currency_more.py").write_text('''from decimal import Decimal as D

import pytest


def test_unknown_currency(catalog, customers):
    from inventory_service.currency import UnsupportedCurrency
    from inventory_service.pricing import quote
    with pytest.raises(UnsupportedCurrency):
        quote(catalog, customers["C1"], [("TOO-0001", 1)], currency="CHF")


def test_order_currency_and_usd_refund_only(svc):
    from inventory_service.models import ValidationError
    o = svc.create_order("C3", [("LIT-0001", 1)], currency="jpy")
    assert o.currency == "JPY"
    svc.ship(o.id)
    with pytest.raises(ValidationError):
        svc.refund(o.id, {"LIT-0001": 1})
''', encoding="utf-8")


def ref_T3(r):
    shutil.copy(SOL / "T3" / "pricing.py", pkg(r, "pricing.py"))
    start_T3(r)


def ref_T6(r):
    shutil.copy(SOL / "T6" / "test_reports.py", r / "tests" / "test_reports.py")


REF = {"T1": lambda r: None, "T2": ref_T2, "T3": ref_T3, "T4": lambda r: None, "T5": lambda r: None, "T6": ref_T6}
START = {"T1": start_T1, "T2": start_T2, "T3": start_T3, "T4": start_T4, "T5": start_T5, "T6": start_T6}

# ---------- T6 mutants: one change each to reports.py ----------
MUTANTS = [
    ("m01_counts_reserved", 'COUNTED_STATUSES = ("shipped", "partially_refunded", "refunded")',
     'COUNTED_STATUSES = ("shipped", "partially_refunded", "refunded", "reserved")'),
    ("m02_sales_ignores_refunds", "            kept = units_sold(order, line.sku)\n            if kept <= 0:",
     "            kept = order.quantity_of(line.sku)\n            if kept <= 0:"),
    ("m03_sales_keeps_zero_categories", "            if kept <= 0:\n                continue\n            cat",
     "            if kept < 0:\n                continue\n            cat"),
    ("m04_top_tie_order_reversed", "key=lambda x: (-x[1], x[0]))", "key=lambda x: (-x[1], [-ord(ch) for ch in x[0]]))"),
    ("m05_top_off_by_one", "    return ranked[:n]", "    return ranked[:n + 1]"),
    ("m06_top_keeps_zero_units", "for s, u in totals.items() if u > 0)", "for s, u in totals.items() if u >= 0)"),
    ("m07_valuation_ignores_inactive_flag", "    for p in catalog.products(include_inactive=include_inactive):",
     "    for p in catalog.products():"),
    ("m08_low_stock_strict", "        if avail <= threshold:", "        if avail < threshold:"),
    ("m09_low_stock_uses_on_hand", "        avail = inventory.available(p.sku)", "        avail = inventory.on_hand(p.sku)"),
    ("m10_aov_ignores_refunds", 'values = [o.totals["total"] - o.refunded_amount() for o',
     'values = [o.totals["total"] for o'),
]


def build():
    for tid, (folder, text) in TASKS.items():
        t = copy_base(B / "tasks" / folder)
        START[tid](t)
        (t / "README.md").write_text(HEADER + text + FOOTER, encoding="utf-8")
        r = copy_base(B / "reference" / tid)
        if tid == "T4":
            (r / "tests" / "test_fulfillment.py").write_text((t / "tests" / "test_fulfillment.py").read_text(encoding="utf-8"),
                                                            encoding="utf-8")
        else:
            REF[tid](r)
        print(f"built tasks/{folder} and reference/{tid}")
    mdir = B / "reference" / "mutants" / "T6"
    mdir.mkdir(parents=True, exist_ok=True)
    src = (BASE / "inventory_service" / "reports.py").read_text(encoding="utf-8")
    for name, old, new in MUTANTS:
        assert src.count(old) == 1, f"mutant {name}: text found {src.count(old)} times"
        (mdir / f"{name}.py").write_text(src.replace(old, new), encoding="utf-8")
    print(f"wrote {len(MUTANTS)} mutants to {mdir}")


if __name__ == "__main__":
    build()
