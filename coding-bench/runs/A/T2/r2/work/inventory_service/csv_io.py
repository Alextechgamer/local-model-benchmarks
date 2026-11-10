"""CSV import of products and stock counts, CSV export of orders.

Imports never stop at a bad row: good rows are applied and each bad row is reported as (line number, message),
where line 1 is the header. Column names are matched case-insensitively and may be in any order.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from .models import ValidationError
from .money import money_str
from .currency import DECIMALS

PRODUCT_COLUMNS = ("sku", "name", "price", "category")      # required
PRODUCT_OPTIONAL = {"weight_kg": "0"}                        # optional, with its default
STOCK_COLUMNS = ("sku", "quantity")
ORDER_EXPORT_COLUMNS = ("order_id", "customer_id", "status", "items", "subtotal", "discount", "tax", "shipping",
                        "total", "refunded", "currency")


@dataclass
class ImportResult:
    added: int = 0
    updated: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def fmt(amount, currency: str) -> str:
    """Amount text for an order's currency: money_str for USD, else the currency's decimals (no code)."""
    code = currency.strip().upper()
    return money_str(amount) if code == "USD" else f"{amount:.{DECIMALS.get(code, 2)}f}"


def _rows(text: str, required: tuple[str, ...]):
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = [h.strip().lower() for h in next(reader)]
    except StopIteration:
        raise ValidationError("the file is empty") from None
    missing = [c for c in required if c not in header]
    if missing:
        raise ValidationError(f"missing column(s): {', '.join(missing)}")
    for n, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) > len(header):
            yield n, None, "too many fields"
            continue
        row = row + [""] * (len(header) - len(row))
        yield n, {h: v.strip() for h, v in zip(header, row)}, None


def import_products(text: str, catalog) -> ImportResult:
    """Add new SKUs and update existing ones from CSV text with columns sku, name, price, category[, weight_kg]."""
    result = ImportResult()
    for n, row, err in _rows(text, PRODUCT_COLUMNS):
        if err:
            result.errors.append((n, err))
            continue
        for col, default in PRODUCT_OPTIONAL.items():
            if not row.get(col):
                row[col] = default
        try:
            sku = row["sku"].upper()
            if sku in catalog:
                catalog.update(sku, row["name"], row["price"], row["category"], row["weight_kg"])
                result.updated += 1
            else:
                catalog.add_product(sku, row["name"], row["price"], row["category"], row["weight_kg"])
                result.added += 1
        except (ValidationError, ValueError) as e:
            result.errors.append((n, str(e)))
    return result


def import_stock(text: str, inventory, catalog=None, mode: str = "set") -> ImportResult:
    """Apply stock counts from CSV text with columns sku, quantity.

    mode "set" replaces the on-hand count (a stock take); mode "add" receives the units. With a catalog, unknown
    SKUs are reported as errors.
    """
    if mode not in ("set", "add"):
        raise ValueError("mode must be 'set' or 'add'")
    result = ImportResult()
    for n, row, err in _rows(text, STOCK_COLUMNS):
        if err:
            result.errors.append((n, err))
            continue
        sku = row["sku"].upper()
        try:
            qty = int(row["quantity"])
        except ValueError:
            result.errors.append((n, f"{sku}: quantity {row['quantity']!r} is not a whole number"))
            continue
        if catalog is not None and sku not in catalog:
            result.errors.append((n, f"unknown SKU {sku}"))
            continue
        try:
            if mode == "set":
                inventory.set_stock(sku, qty)
            else:
                inventory.receive(sku, qty)
            result.updated += 1
        except ValidationError as e:
            result.errors.append((n, str(e)))
    return result


def export_orders(orders) -> str:
    """CSV text with one row per order (sorted by id). items is 'SKU x QTY' joined by '; '. discount is the sum of
    line, tier and coupon discounts; refunded is the total refunded so far."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(ORDER_EXPORT_COLUMNS)
    for order in sorted(orders, key=lambda o: o.id):
        t = order.totals
        discount = t.get("line_discounts", 0) + t.get("tier_discount", 0) + t.get("coupon_discount", 0)
        items = "; ".join(f"{l.sku} x {l.quantity}" for l in order.lines)
        cur = getattr(order, "currency", "USD") or "USD"
        w.writerow([order.id, order.customer_id, order.status, items, fmt(t.get("subtotal", 0), cur),
                    fmt(discount, cur), fmt(t.get("tax", 0), cur), fmt(t.get("shipping", 0), cur),
                    fmt(t.get("total", 0), cur), fmt(order.refunded_amount(), cur), cur])
    return out.getvalue()
