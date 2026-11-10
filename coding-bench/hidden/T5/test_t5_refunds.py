"""Task 5: refunds of orders with tier or coupon discounts must not pay back tax on discounts the customer never paid.

test_task_* fail on the starting code (tax refunded on the amount before order-level discounts).
"""
from decimal import Decimal as D

from _hx import world


def shipped(svc, cid, items, coupon=None):
    o = svc.create_order(cid, items, coupon)
    svc.ship(o.id)
    return o


def test_task_reported_case_coupon_two_of_four_chairs():
    _, _, svc, _ = world()
    o = shipped(svc, "C1", [("GAR-0001", 4)], "SAVE10")
    assert o.totals["total"] == D("147.68")
    r1 = svc.refund(o.id, {"GAR-0001": 2})
    assert r1.amount == D("73.84")
    r2 = svc.refund(o.id, {"GAR-0001": 2})
    assert r2.amount == D("73.84")


def test_task_gold_customer_germany():
    _, _, svc, _ = world()
    o = shipped(svc, "C3", [("TOO-0002", 2), ("KIT-0002", 1)])      # gold 10%, DE 19%
    r = svc.refund(o.id, {"TOO-0002": 1})
    assert r.amount == D("95.32")          # 89.00 - 8.90 tier share = 80.10, + 15.22 tax


def test_task_silver_with_flat_coupon_new_york():
    _, _, svc, _ = world()
    o = shipped(svc, "C2", [("KIT-0002", 2), ("TOO-0001", 1)], "FLAT5")
    r = svc.refund(o.id, {"KIT-0002": 1})
    assert r.amount == D("38.91")          # 39.90 - (4.62 + 5) x 39.90/92.30 = 35.74, + 3.17 tax (NY)


def test_task_partial_refunds_add_up_to_total_with_discounts():
    _, _, svc, _ = world()
    o = shipped(svc, "C5", [("TOO-0002", 3), ("LIT-0001", 2)], "BIG25")
    a = svc.refund(o.id, {"TOO-0002": 1})
    b = svc.refund(o.id, {"LIT-0001": 1, "TOO-0002": 1})
    c = svc.refund(o.id, {"TOO-0002": 1, "LIT-0001": 1})
    assert a.amount == D("64.44")          # 89.00 - 28.92 share = 60.08, + 4.36 tax
    assert a.amount + b.amount + c.amount == o.totals["total"]
    assert b.amount == D("85.75")          # lamp 19.87 + 1.44 tax, drill 60.08 + 4.36 tax


def test_task_refund_one_hose_silver_coupon():
    _, _, svc, _ = world()
    o = shipped(svc, "C2", [("GAR-0002", 4)], "SAVE10")
    r = svc.refund(o.id, {"GAR-0002": 1})
    assert r.amount == D("19.77")          # 21.24 - 3.08 share = 18.16, + 1.61 tax (NY)


def test_keep_refund_without_discounts_unchanged():
    _, _, svc, _ = world()
    o = shipped(svc, "C1", [("TOO-0002", 2)])                      # 178.00 + 12.91 tax, free shipping
    r = svc.refund(o.id, {"TOO-0002": 1})
    assert r.amount == D("95.45")          # 89.00 + 6.45 tax (7.25% of 89.00 = 6.4525)
