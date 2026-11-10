"""Read-only reports over orders, the catalog and the inventory."""
from __future__ import annotations

from decimal import Decimal

from .money import ZERO, round_money

COUNTED_STATUSES = ("shipped", "partially_refunded", "refunded")


def units_sold(order, sku: str) -> int:
    """Units of `sku` the customer kept: bought minus refunded."""
    return order.quantity_of(sku) - order.refunded_quantity(sku)


def sales_by_category(orders, catalog) -> dict[str, Decimal]:
    """Gross sales (unit price x units kept) per category, over shipped and refunded orders.

    Cancelled and still-reserved orders do not count. Categories with no sales are left out. Amounts are rounded
    to the cent.
    """
    out: dict[str, Decimal] = {}
    for order in orders:
        if order.status not in COUNTED_STATUSES:
            continue
        for line in order.lines:
            kept = units_sold(order, line.sku)
            if kept <= 0:
                continue
            cat = catalog.get(line.sku).category
            out[cat] = out.get(cat, ZERO) + line.unit_price * kept
    return {k: round_money(v) for k, v in sorted(out.items())}


def top_products(orders, n: int = 3) -> list[tuple[str, int]]:
    """The n SKUs with the most units kept over counted orders, as (sku, units), most first; ties by SKU A-Z.

    SKUs whose units were all refunded are left out. n larger than the number of SKUs returns them all.
    """
    if n < 0:
        raise ValueError("n cannot be negative")
    totals: dict[str, int] = {}
    for order in orders:
        if order.status not in COUNTED_STATUSES:
            continue
        for line in order.lines:
            totals[line.sku] = totals.get(line.sku, 0) + units_sold(order, line.sku)
    ranked = sorted(((s, u) for s, u in totals.items() if u > 0), key=lambda x: (-x[1], x[0]))
    return ranked[:n]


def inventory_valuation(inventory, catalog, include_inactive: bool = False) -> Decimal:
    """On-hand units x price for catalog SKUs (inactive products only when asked), rounded to the cent."""
    total = ZERO
    for p in catalog.products(include_inactive=include_inactive):
        total += p.price * inventory.on_hand(p.sku)
    return round_money(total)


def low_stock_report(inventory, catalog, threshold: int = 5) -> list[str]:
    """'SKU name: N left' lines for active products whose available units are at or below threshold, by SKU."""
    lines = []
    for p in catalog.products():
        avail = inventory.available(p.sku)
        if avail < threshold:
            lines.append(f"{p.sku} {p.name}: {avail} left")
    return lines


def average_order_value(orders) -> Decimal:
    """Mean of (total - refunded) over counted orders, rounded to the cent; 0.00 when there are none."""
    values = [o.totals["total"] - o.refunded_amount() for o in orders if o.status in COUNTED_STATUSES]
    if not values:
        return round_money(ZERO)
    return round_money(sum(values, ZERO) / len(values))
