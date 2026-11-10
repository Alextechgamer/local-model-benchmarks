# inventory-service

A small Python library and command line tool for an online shop's back office: the product catalog, stock levels and
reservations, orders, pricing (discounts, coupons, tax, shipping), refunds, CSV import/export and JSON storage.

- Package: `inventory_service/`. The module docstrings explain the rules.
- Tests: `tests/`. Run them with `python -m pytest` from this folder.
- Python 3.14, standard library only (pytest for the tests).

## Your task: refactor `pricing.py`

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

Work autonomously; do not wait for approval.
