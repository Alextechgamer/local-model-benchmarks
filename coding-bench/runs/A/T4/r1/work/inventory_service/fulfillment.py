"""Choosing which warehouse ships which part of an order."""
from __future__ import annotations

from .inventory import InsufficientStock


def plan_shipments(lines: list[tuple[str, int]], stock: dict[str, dict[str, int]],
                   priority: list[str]) -> dict[str, list[tuple[str, int]]]:
    """Decide which warehouse ships which units of an order.

    Arguments:
      lines     the order as (sku, quantity) pairs, in order. The same SKU may appear more than once.
      stock     units available per warehouse: {warehouse: {sku: units}}. A missing SKU means 0 units.
      priority  warehouse names, most preferred first. Warehouses not in this list are never used.

    Rules:
      1. Lines are handled one at a time, in the order given. Units taken for an earlier line are no longer
         available to later lines.
      2. A line is shipped from a single warehouse when possible: the first warehouse in `priority` that has
         enough units left for the whole quantity ships all of it.
      3. Otherwise the line is split: walk `priority` in order and take min(units left there, units still needed)
         from each warehouse that has any, until the quantity is covered.
      4. If all warehouses in `priority` together have fewer units left than a line needs, raise
         InsufficientStock(sku, wanted=quantity, available=units left in total) and plan nothing.
      5. A line with quantity 0 is skipped. A negative quantity raises ValueError.
      6. `stock` is not modified.

    Returns {warehouse: [(sku, units), ...]}: each warehouse's entries in the order they were planned, with only
    warehouses that ship something. A warehouse that ships the same SKU for two different lines gets two entries.

    >>> plan_shipments([("ABC-0001", 3)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 9}}, ["west", "east"])
    {'west': [('ABC-0001', 3)]}
    >>> plan_shipments([("ABC-0001", 7)], {"east": {"ABC-0001": 5}, "west": {"ABC-0001": 4}}, ["east", "west"])
    {'east': [('ABC-0001', 5)], 'west': [('ABC-0001', 2)]}
    """
    remaining: dict[str, dict[str, int]] = {w: dict(stock.get(w, {})) for w in dict.fromkeys(priority)}
    plan: dict[str, list[tuple[str, int]]] = {}
    for sku, quantity in lines:
        if quantity < 0:
            raise ValueError(f"{sku}: quantity must not be negative")
        if quantity == 0:
            continue
        available = sum(warehouse.get(sku, 0) for warehouse in remaining.values())
        if available < quantity:
            raise InsufficientStock(sku, wanted=quantity, available=available)
        for w, warehouse in remaining.items():
            if warehouse.get(sku, 0) >= quantity:
                warehouse[sku] -= quantity
                plan.setdefault(w, []).append((sku, quantity))
                break
        else:
            still_needed = quantity
            for w, warehouse in remaining.items():
                have = warehouse.get(sku, 0)
                if have <= 0:
                    continue
                take = min(have, still_needed)
                warehouse[sku] = have - take
                plan.setdefault(w, []).append((sku, take))
                still_needed -= take
                if still_needed == 0:
                    break
    return plan
