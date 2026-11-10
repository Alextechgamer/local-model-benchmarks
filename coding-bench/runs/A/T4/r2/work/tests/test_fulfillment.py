from inventory_service.fulfillment import plan_shipments


def test_one_warehouse_can_ship_the_whole_line():
    assert plan_shipments([("ABC-0001", 3)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}},
                          ["west", "east"]) == {"west": [("ABC-0001", 3)]}


def test_line_is_split_in_priority_order():
    assert plan_shipments([("ABC-0001", 7)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"east": [("ABC-0001", 5)], "west": [("ABC-0001", 2)]}


def test_earlier_line_consumes_stock():
    stock = {"east": {"ABC-0001": 5}}
    assert plan_shipments([("ABC-0001", 3), ("ABC-0001", 2)], stock, ["east"]) == {"east": [("ABC-0001", 3), ("ABC-0001", 2)]}
    assert stock == {"east": {"ABC-0001": 5}}


def test_full_line_skips_partial_warehouse():
    assert plan_shipments([("ABC-0001", 4)], {"east": {"ABC-0001": 2}, "west": {"ABC-0001": 4}},
                          ["east", "west"]) == {"west": [("ABC-0001", 4)]}


def test_warehouses_not_in_priority_are_never_used():
    assert plan_shipments([("ABC-0001", 2)], {"east": {"ABC-0001": 9}, "north": {"ABC-0001": 9}}, ["east"]) == {
        "east": [("ABC-0001", 2)]}


def test_zero_quantity_line_is_skipped():
    assert plan_shipments([("ABC-0001", 0)], {"east": {"ABC-0001": 5}}, ["east"]) == {}


def test_negative_quantity_raises_value_error():
    import pytest
    with pytest.raises(ValueError):
        plan_shipments([("ABC-0001", -1)], {"east": {"ABC-0001": 5}}, ["east"])


def test_insufficient_stock_raises():
    from inventory_service.inventory import InsufficientStock
    import pytest
    with pytest.raises(InsufficientStock) as exc:
        plan_shipments([("ABC-0001", 3), ("ABC-0001", 8)], {"east": {"ABC-0001": 5}, "west": {"XYZ": 2}}, ["east", "west"])
    assert exc.value.sku == "ABC-0001"
    assert exc.value.wanted == 8
    assert exc.value.available == 2


def test_missing_sku_means_zero():
    from inventory_service.inventory import InsufficientStock
    import pytest
    with pytest.raises(InsufficientStock) as exc:
        plan_shipments([("NOPE", 1)], {"east": {}}, ["east"])
    assert exc.value.wanted == 1
    assert exc.value.available == 0
