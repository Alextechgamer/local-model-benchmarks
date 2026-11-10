# inventory-service

A small Python library and command line tool for an online shop's back office: the product catalog, stock levels and
reservations, orders, pricing (discounts, coupons, tax, shipping), refunds, CSV import/export and JSON storage.

- Package: `inventory_service/`. The module docstrings explain the rules.
- Tests: `tests/`. Run them with `python -m pytest` from this folder.
- Python 3.14, standard library only (pytest for the tests).

## Your task: a bug report from finance

> **Ticket #4471, from the finance team**
>
> Refunds don't add up. Example: order O1001, customer C1 (standard tier, California), 4 x Garden Chair (GAR-0001)
> with the coupon SAVE10. The customer paid $147.68 in total. They returned 2 chairs and we refunded $74.40. Later
> they returned the other 2 and we refunded $73.28. Half of the order should have been $73.84 each time. We only see
> this on orders that had a coupon or a customer-tier discount; orders without discounts look fine.

Find the cause and fix it.

Work autonomously; do not wait for approval.
