from inventory_service.fulfillment import plan_shipments


def test_one_warehouse_can_ship_the_whole_line():
    assert plan_shipments([("ABC-0001", 3)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["west", "east"]) == {"west": [("ABC-0001", 3)]}


def test_line_is_split_in_priority_order():
    assert plan_shipments([("ABC-0001", 7)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"east": [("ABC-0001", 5)], "west": [("ABC-0001", 2)]}
import pytest

from inventory_service.inventory import InsufficientStock


def test_same_sku_appears_in_two_lines_as_two_entries():
    assert plan_shipments([("ABC-0001", 2), ("ABC-0001", 3)],
                          {"east": {"ABC-0001": 5}}, ["east"]) == {
        "east": [("ABC-0001", 2), ("ABC-0001", 3)]}


def test_units_are_consumed_before_later_lines():
    assert plan_shipments([("ABC-0001", 4), ("ABC-0001", 4)],
                          {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 3}}, ["east", "west"]) == {
        "east": [("ABC-0001", 4), ("ABC-0001", 1)], "west": [("ABC-0001", 3)]}
    assert plan_shipments([("ABC-0001", 5), ("ABC-0001", 1)],
                          {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 1}}, ["east", "west"]) == {
        "east": [("ABC-0001", 5)], "west": [("ABC-0001", 1)]}


def test_zero_quantity_skipped_and_negative_quantity_rejected():
    assert plan_shipments([("ABC-0001", 0)], {"east": {"ABC-0001": 5}}, ["east"]) == {}
    with pytest.raises(ValueError):
        plan_shipments([("ABC-0001", -1)], {"east": {"ABC-0001": 5}}, ["east"])


def test_insufficient_stock_reports_total_left():
    with pytest.raises(InsufficientStock) as exc:
        plan_shipments([("ABC-0001", 8)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 2}},
                       ["east", "west"])
    assert exc.value.sku == "ABC-0001"
    assert exc.value.wanted == 8
    assert exc.value.available == 7


def test_stock_is_not_modified_and_unlisted_warehouses_are_ignored():
    stock = {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}, "south": {"ABC-0001": 100}}
    assert plan_shipments([("ABC-0001", 4)], stock, ["west", "east"]) == {"west": [("ABC-0001", 4)]}
    assert stock == {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}, "south": {"ABC-0001": 100}}
