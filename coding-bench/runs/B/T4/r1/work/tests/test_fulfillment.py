import pytest

from inventory_service.fulfillment import plan_shipments
from inventory_service.inventory import InsufficientStock


def test_one_warehouse_can_ship_the_whole_line():
    assert plan_shipments([("ABC-0001", 3)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["west", "east"]) == {"west": [("ABC-0001", 3)]}


def test_line_is_split_in_priority_order():
    assert plan_shipments([("ABC-0001", 7)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"east": [("ABC-0001", 5)], "west": [("ABC-0001", 2)]}


def test_single_warehouse_preferred_even_when_earlier_one_has_some():
    # "a" has 3 (not enough for 5), "b" has 5 (enough). Ship the whole line from "b", not split.
    assert plan_shipments([("S", 5)], {"a": {"S": 3}, "b": {"S": 5}}, ["a", "b"]) == {"b": [("S", 5)]}


def test_earlier_lines_consume_stock_for_later_lines():
    stock = {"w": {"S": 10}}
    assert plan_shipments([("S", 6), ("S", 4)], stock, ["w"]) == {"w": [("S", 6), ("S", 4)]}
    # The same total now fails: not enough left.
    with pytest.raises(InsufficientStock) as e:
        plan_shipments([("S", 6), ("S", 5)], stock, ["w"])
    assert (e.value.sku, e.value.wanted, e.value.available) == ("S", 5, 4)


def test_same_sku_two_lines_same_warehouse_gives_two_entries():
    assert plan_shipments([("S", 2), ("S", 2)], {"w": {"S": 10}}, ["w"]) == {"w": [("S", 2), ("S", 2)]}


def test_zero_quantity_line_is_skipped():
    assert plan_shipments([("S", 0), ("T", 2)], {"w": {"T": 5}}, ["w"]) == {"w": [("T", 2)]}
    assert plan_shipments([], {"w": {}}, ["w"]) == {}
    assert plan_shipments([("S", 0)], {"w": {"S": 5}}, ["w"]) == {}


def test_negative_quantity_raises_value_error():
    with pytest.raises(ValueError):
        plan_shipments([("S", -1)], {"w": {"S": 5}}, ["w"])


def test_insufficient_stock_reports_total_available():
    with pytest.raises(InsufficientStock) as e:
        plan_shipments([("S", 10)], {"a": {"S": 3}, "b": {"S": 4}}, ["a", "b"])
    assert (e.value.sku, e.value.wanted, e.value.available) == ("S", 10, 7)


def test_stock_is_not_modified():
    stock = {"a": {"S": 5}, "b": {"S": 4}}
    snapshot = {w: dict(s) for w, s in stock.items()}
    plan_shipments([("S", 8)], stock, ["a", "b"])
    assert stock == snapshot


def test_warehouses_not_in_priority_are_never_used():
    assert plan_shipments([("S", 3)], {"north": {"S": 100}, "south": {"S": 3}}, ["south"]) \
        == {"south": [("S", 3)]}


def test_priority_warehouse_missing_from_stock_counts_as_zero():
    assert plan_shipments([("S", 2)], {"a": {}, "b": {"S": 5}}, ["a", "b"]) == {"b": [("S", 2)]}


def test_missing_sku_counts_as_zero_and_can_still_split():
    assert plan_shipments([("S", 5)], {"a": {}, "b": {"S": 2}, "c": {"S": 4}}, ["a", "b", "c"]) \
        == {"b": [("S", 2)], "c": [("S", 3)]}


def test_split_across_three_warehouses():
    assert plan_shipments([("S", 9)], {"a": {"S": 2}, "b": {"S": 3}, "c": {"S": 6}}, ["a", "b", "c"]) \
        == {"a": [("S", 2)], "b": [("S", 3)], "c": [("S", 4)]}


def test_empty_priority_and_empty_lines():
    assert plan_shipments([], {}, []) == {}
    with pytest.raises(InsufficientStock):
        plan_shipments([("S", 1)], {"w": {"S": 5}}, [])
