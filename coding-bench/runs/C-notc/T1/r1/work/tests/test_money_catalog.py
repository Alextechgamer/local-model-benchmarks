from decimal import Decimal

import pytest

from inventory_service.catalog import Catalog, normalize_category
from inventory_service.models import ValidationError
from inventory_service.money import allocate_proportionally, money_str, round_money, split_evenly, to_decimal


def test_round_money_half_up():
    assert round_money("2.345") == Decimal("2.35")
    assert round_money("2.344") == Decimal("2.34")
    assert round_money("-2.345") == Decimal("-2.35")


def test_to_decimal_float_and_bad_input():
    assert to_decimal(0.1) == Decimal("0.1")
    with pytest.raises(ValueError):
        to_decimal("abc")
    with pytest.raises(TypeError):
        to_decimal(True)


def test_split_and_allocate():
    assert split_evenly("10.00", 3) == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]
    assert sum(allocate_proportionally("10.00", [1, 1, 1])) == Decimal("10.00")
    assert allocate_proportionally("1.00", [3, 1]) == [Decimal("0.75"), Decimal("0.25")]
    assert money_str(Decimal("3")) == "3.00"


def test_add_and_search(catalog):
    assert len(catalog) == 6
    assert [p.sku for p in catalog.search(category="Garden")] == ["GAR-0001", "GAR-0002"]
    assert [p.sku for p in catalog.search(text="lamp")] == ["LIT-0001"]
    catalog.deactivate("KIT-0001")
    assert "KIT-0001" not in [p.sku for p in catalog.products()]
    assert catalog.categories() == ["garden", "lighting", "tools"]


@pytest.mark.parametrize("sku", ["AB-1234", "ABCD-123", "abc_1234", ""])
def test_bad_sku(sku):
    with pytest.raises(ValidationError):
        Catalog().add_product(sku, "x", "1.00", "misc")


def test_price_and_duplicates(catalog):
    with pytest.raises(ValidationError):
        catalog.add_product("TOO-0001", "Again", "1.00", "tools")
    with pytest.raises(ValidationError):
        catalog.update_price("TOO-0001", "0")
    assert catalog.update_price("TOO-0001", "13.00").price == Decimal("13.00")
    assert normalize_category("  Garden   Tools ") == "garden tools"
