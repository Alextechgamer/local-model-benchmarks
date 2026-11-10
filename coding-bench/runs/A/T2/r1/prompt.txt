# inventory-service

A small Python library and command line tool for an online shop's back office: the product catalog, stock levels and
reservations, orders, pricing (discounts, coupons, tax, shipping), refunds, CSV import/export and JSON storage.

- Package: `inventory_service/`. The module docstrings explain the rules.
- Tests: `tests/`. Run them with `python -m pytest` from this folder.
- Python 3.14, standard library only (pytest for the tests).

## Your task: multi-currency pricing

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

Work autonomously; do not wait for approval.
