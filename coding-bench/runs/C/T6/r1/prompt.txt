# inventory-service

A small Python library and command line tool for an online shop's back office: the product catalog, stock levels and
reservations, orders, pricing (discounts, coupons, tax, shipping), refunds, CSV import/export and JSON storage.

- Package: `inventory_service/`. The module docstrings explain the rules.
- Tests: `tests/`. Run them with `python -m pytest` from this folder.
- Python 3.14, standard library only (pytest for the tests).

## Your task: write tests for `reports.py`

`inventory_service/reports.py` has no tests. Write them in `tests/test_reports.py`.

- Test the behaviour its docstrings describe, so that any change that breaks it makes at least one of your tests
  fail.
- Your tests must pass on the current code. Do not change `reports.py` or any other module.
- You may use the fixtures in `tests/conftest.py`.

Your tests are scored by mutation testing: small deliberate bugs are put into `reports.py` one at a time, and each
one that makes at least one of your tests fail counts.

Work autonomously; do not wait for approval.
