import pytest

from inventory_service.fulfillment import plan_shipments
from inventory_service.inventory import InsufficientStock


def test_one_warehouse_can_ship_the_whole_line():
    assert plan_shipments([("ABC-0001", 3)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["west", "east"]) == {"west": [("ABC-0001", 3)]}


def test_line_is_split_in_priority_order():
    assert plan_shipments([("ABC-0001", 7)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"east": [("ABC-0001", 5)], "west": [("ABC-0001", 2)]}


def test_units_taken_by_earlier_lines_are_gone_for_later_lines():
    assert plan_shipments([("ABC-0001", 3), ("ABC-0001", 4)],
                          {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["west", "east"]) == {"west": [("ABC-0001", 3), ("ABC-0001", 4)]}


def test_units_taken_by_earlier_lines_force_a_later_split():
    assert plan_shipments([("ABC-0001", 5), ("ABC-0001", 4)],
                          {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["east", "west"]) == {"east": [("ABC-0001", 5)],
                                                "west": [("ABC-0001", 4)]}


def test_warehouses_not_in_priority_are_never_used():
    assert plan_shipments([("ABC-0001", 2)],
                          {"east": {"ABC-0001": 5}, "north": {"ABC-0001": 50}},
                          ["east"]) == {"east": [("ABC-0001", 2)]}


def test_missing_sku_in_a_warehouse_means_zero_units():
    assert plan_shipments([("ABC-0001", 6)],
                          {"east": {"XYZ-9999": 50}, "west": {"ABC-0001": 4}, "south": {"ABC-0001": 2}},
                          ["east", "west", "south"]) == {"west": [("ABC-0001", 4)], "south": [("ABC-0001", 2)]}


def test_insufficient_stock_raises_with_totals_and_plans_nothing():
    stock = {"east": {"ABC-0001": 2}, "west": {"ABC-0001": 1}}
    with pytest.raises(InsufficientStock) as excinfo:
        plan_shipments([("ABC-0001", 2), ("ABC-0001", 3)], stock, ["east", "west"])
    assert excinfo.value.sku == "ABC-0001"
    assert excinfo.value.wanted == 3
    assert excinfo.value.available == 1
    assert stock == {"east": {"ABC-0001": 2}, "west": {"ABC-0001": 1}}


def test_zero_quantity_line_is_skipped():
    assert plan_shipments([("ABC-0001", 0), ("ABC-0001", 2)],
                          {"east": {"ABC-0001": 5}},
                          ["east"]) == {"east": [("ABC-0001", 2)]}


def test_negative_quantity_raises_value_error():
    with pytest.raises(ValueError):
        plan_shipments([("ABC-0001", -1)], {"east": {"ABC-0001": 5}}, ["east"])


def test_stock_is_not_modified():
    stock = {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}}
    plan_shipments([("ABC-0001", 7)], stock, ["east", "west"])
    assert stock == {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}}


def test_same_sku_on_two_lines_gives_two_entries():
    assert plan_shipments([("ABC-0001", 2), ("ABC-0001", 3)],
                          {"east": {"ABC-0001": 5}},
                          ["east"]) == {"east": [("ABC-0001", 2), ("ABC-0001", 3)]}


def test_warehouses_that_ship_nothing_are_absent_from_the_result():
    assert plan_shipments([("ABC-0001", 1), ("XYZ-9999", 2)],
                          {"east": {"ABC-0001": 1}, "west": {"XYZ-9999": 2}, "north": {"ABC-0001": 9}},
                          ["east", "west", "north"]) == {"east": [("ABC-0001", 1)], "west": [("XYZ-9999", 2)]}


def test_exactly_enough_units_across_priority_warehouses():
    assert plan_shipments([("ABC-0001", 5)],
                          {"east": {"ABC-0001": 2}, "west": {"ABC-0001": 3}},
                          ["east", "west"]) == {"east": [("ABC-0001", 2)], "west": [("ABC-0001", 3)]}
