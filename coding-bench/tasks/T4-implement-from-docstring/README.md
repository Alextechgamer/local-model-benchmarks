# inventory-service

A small Python library and command line tool for an online shop's back office: the product catalog, stock levels and
reservations, orders, pricing (discounts, coupons, tax, shipping), refunds, CSV import/export and JSON storage.

- Package: `inventory_service/`. The module docstrings explain the rules.
- Tests: `tests/`. Run them with `python -m pytest` from this folder.
- Python 3.14, standard library only (pytest for the tests).

## Your task: implement `plan_shipments`

`plan_shipments` in `inventory_service/fulfillment.py` only raises `NotImplementedError`. Implement it. Its docstring
is the specification: follow every rule in it. `tests/test_fulfillment.py` has the docstring's examples; add more
tests of your own if you like.

Work autonomously; do not wait for approval.
