from inventory_service.fulfillment import plan_shipments
from inventory_service.inventory import InsufficientStock


def test_one_warehouse_can_ship_the_whole_line():
    assert plan_shipments([("ABC-0001", 3)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["west", "east"]) == {"west": [("ABC-0001", 3)]}


def test_line_is_split_in_priority_order():
    assert plan_shipments([("ABC-0001", 7)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"east": [("ABC-0001", 5)], "west": [("ABC-0001", 2)]}


def test_earlier_line_consumes_stock_for_later_lines():
    stock = {"east": {"ABC-0001": 5}}
    assert plan_shipments([("ABC-0001", 3), ("ABC-0001", 2)], stock, ["east"]) == {
        "east": [("ABC-0001", 3), ("ABC-0001", 2)]}
    assert stock == {"east": {"ABC-0001": 5}}


def test_partial_take_leaves_nothing_for_later_lines():
    stock = {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}}
    assert plan_shipments([("ABC-0001", 7), ("ABC-0001", 2)], stock, ["east", "west"]) == {
        "east": [("ABC-0001", 5)], "west": [("ABC-0001", 2), ("ABC-0001", 2)]}


def test_insufficient_stock_raises_with_totals():
    try:
        plan_shipments([("ABC-0001", 6)], {"east": {"ABC-0001": 2}, "west": {"ABC-0001": 3}}, ["east", "west"])
    except InsufficientStock as e:
        assert (e.sku, e.wanted, e.available) == ("ABC-0001", 6, 5)
    else:
        raise AssertionError("expected InsufficientStock")


def test_missing_sku_counts_as_zero():
    try:
        plan_shipments([("ZZZ-9999", 1)], {"east": {"ABC-0001": 2}}, ["east"])
    except InsufficientStock as e:
        assert (e.sku, e.wanted, e.available) == ("ZZZ-9999", 1, 0)
    else:
        raise AssertionError("expected InsufficientStock")


def test_warehouses_outside_priority_are_never_used():
    assert plan_shipments([("ABC-0001", 1)], {"east": {"ABC-0001": 1}, "north": {"ABC-0001": 5}},
                          ["east"]) == {"east": [("ABC-0001", 1)]}


def test_zero_quantity_line_is_skipped():
    assert plan_shipments([("ABC-0001", 0)], {"east": {"ABC-0001": 2}}, ["east"]) == {}


def test_negative_quantity_raises_value_error():
    try:
        plan_shipments([("ABC-0001", -1)], {"east": {"ABC-0001": 2}}, ["east"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_same_sku_from_two_lines_gives_two_entries():
    assert plan_shipments([("ABC-0001", 2), ("ABC-0001", 1)], {"east": {"ABC-0001": 5}},
                          ["east"]) == {"east": [("ABC-0001", 2), ("ABC-0001", 1)]}


def test_skips_warehouse_that_cannot_ship_whole_line_if_one_can():
    assert plan_shipments([("ABC-0001", 4)], {"east": {"ABC-0001": 2}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"west": [("ABC-0001", 4)]}


def test_empty_lines_gives_empty_plan():
    assert plan_shipments([], {"east": {"ABC-0001": 2}}, ["east"]) == {}
