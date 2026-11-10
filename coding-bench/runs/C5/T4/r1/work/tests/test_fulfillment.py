from inventory_service.fulfillment import plan_shipments
from inventory_service.inventory import InsufficientStock


def test_one_warehouse_can_ship_the_whole_line():
    assert plan_shipments([("ABC-0001", 3)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["west", "east"]) == {"west": [("ABC-0001", 3)]}


def test_line_is_split_in_priority_order():
    assert plan_shipments([("ABC-0001", 7)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"east": [("ABC-0001", 5)], "west": [("ABC-0001", 2)]}


def test_earlier_lines_consume_stock_before_later_lines():
    assert plan_shipments([("A", 3), ("A", 2)], {"east": {"A": 5}}, ["east"]) == {
        "east": [("A", 3), ("A", 2)]
    }


def test_split_skips_warehouses_with_none_left():
    assert plan_shipments([("A", 6)], {"east": {"A": 0}, "west": {"A": 4}, "north": {"A": 2}},
                          ["east", "west", "north"]) == {"west": [("A", 4)], "north": [("A", 2)]}


def test_warehouses_not_in_priority_are_ignored():
    assert plan_shipments([("A", 2)], {"east": {"A": 2}, "west": {"A": 10}}, ["east"]) == {
        "east": [("A", 2)]
    }


def test_zero_quantity_is_skipped():
    assert plan_shipments([("A", 0), ("B", 2)], {"east": {"B": 2}}, ["east"]) == {
        "east": [("B", 2)]
    }


def test_negative_quantity_raises_value_error():
    try:
        plan_shipments([("A", -1)], {"east": {"A": 5}}, ["east"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_insufficient_stock_reports_remaining_total():
    try:
        plan_shipments([("A", 6)], {"east": {"A": 2}, "west": {"A": 3}}, ["east", "west"])
    except InsufficientStock as exc:
        assert exc.sku == "A" and exc.wanted == 6 and exc.available == 5
    else:
        raise AssertionError("expected InsufficientStock")


def test_stock_argument_is_not_modified():
    stock = {"east": {"A": 5}, "west": {"A": 4}}
    plan_shipments([("A", 7)], stock, ["east", "west"])
    assert stock == {"east": {"A": 5}, "west": {"A": 4}}
