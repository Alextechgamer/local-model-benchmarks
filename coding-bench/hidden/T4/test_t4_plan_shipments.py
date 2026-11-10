"""Task 4: plan_shipments, implemented from its docstring. Every test_task_* fails on the stub (NotImplementedError)."""
import copy

import pytest

A, B, C = "AAA-0001", "BBB-0002", "CCC-0003"


def plan(lines, stock, priority):
    from inventory_service.fulfillment import plan_shipments
    return plan_shipments(lines, stock, priority)


def test_task_docstring_examples():
    assert plan([(A, 3)], {"east": {A: 5}, "west": {A: 9}}, ["west", "east"]) == {"west": [(A, 3)]}
    assert plan([(A, 7)], {"east": {A: 5}, "west": {A: 4}}, ["east", "west"]) == {"east": [(A, 5)], "west": [(A, 2)]}


def test_task_whole_line_skips_a_preferred_warehouse_that_is_short():
    stock = {"n": {A: 2}, "s": {A: 6}, "w": {A: 10}}
    assert plan([(A, 5)], stock, ["n", "s", "w"]) == {"s": [(A, 5)]}


def test_task_split_walks_priority_and_stops_when_covered():
    stock = {"n": {A: 2}, "s": {A: 3}, "w": {A: 4}}
    assert plan([(A, 6)], stock, ["n", "s", "w"]) == {"n": [(A, 2)], "s": [(A, 3)], "w": [(A, 1)]}
    assert plan([(A, 5)], stock, ["w", "s", "n"]) == {"w": [(A, 4)], "s": [(A, 1)]}


def test_task_split_skips_empty_warehouses():
    stock = {"n": {}, "s": {A: 3}, "w": {A: 0}, "e": {A: 2}}
    assert plan([(A, 5)], stock, ["n", "s", "w", "e"]) == {"s": [(A, 3)], "e": [(A, 2)]}


def test_task_earlier_lines_use_up_stock():
    stock = {"n": {A: 5}, "s": {A: 5}}
    assert plan([(A, 4), (A, 4)], stock, ["n", "s"]) == {"n": [(A, 4)], "s": [(A, 4)]}
    assert plan([(A, 4), (A, 3)], stock, ["n", "s"]) == {"n": [(A, 4)], "s": [(A, 3)]}
    assert plan([(A, 4), (A, 6)], stock, ["n", "s"]) == {"n": [(A, 4), (A, 1)], "s": [(A, 5)]}


def test_task_multiple_skus_keep_planning_order():
    stock = {"n": {A: 1, B: 9}, "s": {A: 9, C: 2}}
    assert plan([(A, 3), (B, 2), (C, 2), (A, 1)], stock, ["n", "s"]) == {
        "s": [(A, 3), (C, 2)], "n": [(B, 2), (A, 1)]}


def test_task_warehouse_with_same_sku_for_two_lines_gets_two_entries():
    assert plan([(A, 1), (B, 1), (A, 2)], {"n": {A: 5, B: 5}}, ["n"]) == {"n": [(A, 1), (B, 1), (A, 2)]}


def test_task_unlisted_warehouses_are_never_used():
    stock = {"n": {A: 1}, "secret": {A: 100}}
    assert plan([(A, 1)], stock, ["n"]) == {"n": [(A, 1)]}
    from inventory_service.inventory import InsufficientStock
    with pytest.raises(InsufficientStock):
        plan([(A, 2)], stock, ["n"])


def test_task_insufficient_stock_reports_totals():
    from inventory_service.inventory import InsufficientStock
    with pytest.raises(InsufficientStock) as e:
        plan([(B, 2), (A, 10)], {"n": {A: 3, B: 2}, "s": {A: 4}}, ["n", "s"])
    assert (e.value.sku, e.value.wanted, e.value.available) == (A, 10, 7)


def test_task_insufficient_after_earlier_lines():
    from inventory_service.inventory import InsufficientStock
    with pytest.raises(InsufficientStock) as e:
        plan([(A, 4), (A, 3)], {"n": {A: 3}, "s": {A: 3}}, ["n", "s"])
    assert (e.value.wanted, e.value.available) == (3, 2)


def test_task_zero_skipped_negative_rejected():
    assert plan([(A, 0), (B, 1)], {"n": {B: 1}}, ["n"]) == {"n": [(B, 1)]}
    assert plan([(A, 0)], {"n": {}}, ["n"]) == {}
    with pytest.raises(ValueError):
        plan([(A, -1)], {"n": {A: 5}}, ["n"])


def test_task_stock_is_not_modified():
    stock = {"n": {A: 2}, "s": {A: 4, B: 1}}
    before = copy.deepcopy(stock)
    plan([(A, 5), (B, 1)], stock, ["n", "s"])
    assert stock == before


def test_task_warehouse_missing_from_stock_counts_as_empty():
    assert plan([(A, 2)], {"s": {A: 2}}, ["ghost", "s"]) == {"s": [(A, 2)]}
