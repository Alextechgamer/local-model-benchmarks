from decimal import Decimal as D

import pytest

from inventory_service.inventory import InsufficientStock, Inventory
from inventory_service.models import ValidationError


def test_reserve_and_available(inventory):
    inventory.reserve("O1", "TOO-0001", 20)
    assert inventory.available("TOO-0001") == 30
    with pytest.raises(InsufficientStock):
        inventory.reserve("O2", "TOO-0001", 31)


def test_release_frees_every_line_of_an_order(inventory):
    inventory.reserve("O1", "TOO-0001", 5)
    inventory.reserve("O1", "GAR-0001", 7)
    assert inventory.release("O1") == 12
    assert inventory.available("TOO-0001") == 50
    assert inventory.available("GAR-0001") == 50


def test_commit_and_stock_take(inventory):
    inventory.reserve("O1", "LIT-0001", 4)
    assert inventory.commit("O1") == {"LIT-0001": 4}
    assert inventory.on_hand("LIT-0001") == 46
    inventory.reserve("O2", "LIT-0001", 6)
    with pytest.raises(ValidationError):
        inventory.set_stock("LIT-0001", 5)


def test_expiry_uses_the_clock(clock):
    inv = Inventory(clock)
    inv.receive("TOO-0001", 10)
    inv.reserve("O1", "TOO-0001", 3)
    clock.t += 100
    inv.reserve("O2", "TOO-0001", 3)
    clock.t += 50
    assert inv.expire_reservations(120) == ["O1"]
    assert inv.available("TOO-0001") == 7


def test_create_ship_cancel(svc, inventory):
    o = svc.create_order("C1", [("TOO-0001", 2), ("KIT-0001", 1), ("TOO-0001", 1)])
    assert [(l.sku, l.quantity) for l in o.lines] == [("TOO-0001", 3), ("KIT-0001", 1)]
    assert inventory.available("TOO-0001") == 47
    svc.ship(o.id)
    assert inventory.on_hand("TOO-0001") == 47
    with pytest.raises(ValidationError):
        svc.cancel(o.id)
    o2 = svc.create_order("C1", [("GAR-0002", 2)])
    svc.cancel(o2.id)
    assert inventory.available("GAR-0002") == 50


def test_failed_order_reserves_nothing(svc, inventory):
    with pytest.raises(InsufficientStock):
        svc.create_order("C1", [("TOO-0001", 5), ("TOO-0002", 99)])
    assert inventory.available("TOO-0001") == 50


def test_refund_without_order_discounts(svc, inventory):
    o = svc.create_order("C4", [("TOO-0002", 2)])          # Oregon: no tax
    svc.ship(o.id)
    r = svc.refund(o.id, {"TOO-0002": 1})
    assert r.amount == D("89.00")
    assert inventory.on_hand("TOO-0002") == 49
    assert o.status == "partially_refunded"
    r2 = svc.refund(o.id, {"TOO-0002": 1}, restock=False)
    assert o.status == "refunded"
    assert r.amount + r2.amount == o.totals["total"]
    with pytest.raises(ValidationError):
        svc.refund(o.id, {"TOO-0002": 1})


def test_refund_with_coupon_taxes_the_discounted_amount(svc, inventory):
    o = svc.create_order("C1", [("GAR-0001", 4)], coupon="SAVE10")
    svc.ship(o.id)
    assert o.totals["total"] == D("147.68")
    r1 = svc.refund(o.id, {"GAR-0001": 2})
    r2 = svc.refund(o.id, {"GAR-0001": 2})
    assert r1.amount == D("73.84")
    assert r2.amount == D("73.84")
    assert r1.amount + r2.amount == o.totals["total"]
