"""Order lifecycle: create (reserve stock), cancel (release), ship (commit) and refund.

A refund gives back what the customer paid for the returned units:
  - the units' share of their line after the line discount (by quantity),
  - minus their share of the order-level discounts (tier + coupon), in proportion to the line amounts after line
    discounts,
  - plus the tax on that amount at the order's region rate,
  - plus the shipping charge, only when the refund returns everything that is left on the order.
A refund that returns everything left on the order pays exactly what is left of the order total, so the refunds of
an order add up to its total; no refund ever pays more than what is left.
"""
from __future__ import annotations

import itertools
from decimal import Decimal

from .models import Order, OrderLine, Refund, ValidationError
from .money import ZERO, percent_of, round_money
from .pricing import TAX_RATES, compute_order_total


class OrderService:
    def __init__(self, catalog, inventory, customers: dict | None = None):
        self.catalog = catalog
        self.inventory = inventory
        self.customers = customers if customers is not None else {}
        self.orders: dict[str, Order] = {}
        self._order_ids = itertools.count(1001)
        self._refund_ids = itertools.count(1)

    def add_customer(self, customer) -> None:
        if customer.id in self.customers:
            raise ValidationError(f"customer {customer.id} already exists")
        self.customers[customer.id] = customer

    def get(self, order_id: str) -> Order:
        try:
            return self.orders[order_id]
        except KeyError:
            raise ValidationError(f"unknown order {order_id}") from None

    def create_order(self, customer_id: str, items: list[tuple[str, int]], coupon: str | None = None) -> Order:
        """Price the items at catalog prices and reserve their stock. Nothing is reserved if any line fails."""
        customer = self.customers.get(customer_id)
        if customer is None:
            raise ValidationError(f"unknown customer {customer_id}")
        merged: dict[str, int] = {}
        for sku, qty in items:
            if qty <= 0:
                raise ValidationError(f"{sku}: quantity must be positive")
            merged[sku] = merged.get(sku, 0) + qty
        lines = []
        for sku, qty in merged.items():
            product = self.catalog.get(sku)
            if not product.active:
                raise ValidationError(f"{sku} is not for sale")
            lines.append(OrderLine(sku, qty, product.price))
        breakdown = compute_order_total(lines, self.catalog, customer, coupon)
        order_id = f"O{next(self._order_ids)}"
        try:
            for line in lines:
                self.inventory.reserve(order_id, line.sku, line.quantity)
        except ValidationError:
            self.inventory.release(order_id)
            raise
        order = Order(order_id, customer_id, lines, customer.region, coupon.strip().upper() if coupon else None,
                      "reserved", breakdown.to_dict())
        self.orders[order_id] = order
        return order

    def cancel(self, order_id: str) -> Order:
        order = self.get(order_id)
        if order.status != "reserved":
            raise ValidationError(f"order {order_id} is {order.status}; only reserved orders can be cancelled")
        self.inventory.release(order_id)
        order.status = "cancelled"
        return order

    def ship(self, order_id: str) -> Order:
        order = self.get(order_id)
        if order.status != "reserved":
            raise ValidationError(f"order {order_id} is {order.status}; only reserved orders can ship")
        self.inventory.commit(order_id)
        order.status = "shipped"
        return order

    def _line_net(self, order: Order, sku: str, qty: int) -> Decimal:
        """The returned units' share of their line after the line discount, by quantity."""
        breakdown = compute_order_total(order.lines, self.catalog, self.customers[order.customer_id],
                                         order.coupon, order.region)
        detail = next(d for d in breakdown.lines if d["sku"] == sku)
        return round_money(detail["net"] * qty / detail["quantity"])

    def refund_amount(self, order: Order, quantities: dict[str, int]) -> Decimal:
        """What a refund of `quantities` ({sku: units}) pays back; see the module docstring."""
        totals = order.totals
        after_lines = totals["subtotal"] - totals["line_discounts"]
        order_discounts = totals["tier_discount"] + totals["coupon_discount"]
        rate = TAX_RATES[order.region]
        amount = ZERO
        for sku, qty in quantities.items():
            net = self._line_net(order, sku, qty)
            share = round_money(order_discounts * net / after_lines) if after_lines else ZERO
            taxable = net - share
            amount += taxable + round_money(percent_of(taxable, rate))
        left_after = {l.sku: l.quantity - order.refunded_quantity(l.sku) - quantities.get(l.sku, 0) for l in order.lines}
        remaining = totals["total"] - order.refunded_amount()
        if all(v == 0 for v in left_after.values()):
            return remaining                     # the last refund: shipping and every rounding cent that is left
        return min(amount, remaining)

    def refund(self, order_id: str, quantities: dict[str, int], restock: bool = True) -> Refund:
        """Refund returned units of a shipped order; optionally put them back in stock."""
        order = self.get(order_id)
        if order.status not in ("shipped", "partially_refunded"):
            raise ValidationError(f"order {order_id} is {order.status}; only shipped orders can be refunded")
        if not quantities or any(q <= 0 for q in quantities.values()):
            raise ValidationError("a refund needs positive quantities")
        for sku, qty in quantities.items():
            bought = order.quantity_of(sku)
            if bought == 0:
                raise ValidationError(f"{sku} is not on order {order_id}")
            if qty > bought - order.refunded_quantity(sku):
                raise ValidationError(f"{sku}: only {bought - order.refunded_quantity(sku)} left to refund")
        amount = self.refund_amount(order, quantities)
        refund = Refund(f"F{next(self._refund_ids)}", order_id, dict(quantities), amount, restock)
        order.refunds.append(refund)
        if restock:
            for sku, qty in quantities.items():
                self.inventory.restock(sku, qty)
        fully = all(order.refunded_quantity(l.sku) == l.quantity for l in order.lines)
        order.status = "refunded" if fully else "partially_refunded"
        return refund

    def to_dict(self) -> dict:
        return {"orders": [o.to_dict() for o in self.orders.values()],
                "next_order": int(max([int(i[1:]) for i in self.orders] or [1000])) + 1,
                "next_refund": 1 + sum(len(o.refunds) for o in self.orders.values())}

    def load_orders(self, d: dict) -> None:
        self.orders = {o["id"]: Order.from_dict(o) for o in d.get("orders", [])}
        self._order_ids = itertools.count(int(d.get("next_order", 1001)))
        self._refund_ids = itertools.count(int(d.get("next_refund", 1)))
