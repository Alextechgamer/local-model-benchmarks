"""Stock levels and reservations.

on_hand is what is physically in the warehouse. A reservation holds units for an order until it ships (commit) or is
cancelled (release). available = on_hand - reserved. The clock is injected so reservation ages are testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import ValidationError


class InsufficientStock(ValidationError):
    def __init__(self, sku: str, wanted: int, available: int):
        super().__init__(f"{sku}: wanted {wanted}, only {available} available")
        self.sku, self.wanted, self.available = sku, wanted, available


@dataclass
class Reservation:
    id: str
    order_id: str
    sku: str
    quantity: int
    created_at: float

    def to_dict(self) -> dict:
        return {"id": self.id, "order_id": self.order_id, "sku": self.sku, "quantity": self.quantity,
                "created_at": self.created_at}


class Inventory:
    def __init__(self, clock=None):
        self._clock = clock or (lambda: 0.0)
        self._on_hand: dict[str, int] = {}
        self._reservations: dict[str, Reservation] = {}
        self._next_id = 1

    # stock levels
    def on_hand(self, sku: str) -> int:
        return self._on_hand.get(sku, 0)

    def reserved(self, sku: str) -> int:
        return sum(r.quantity for r in self._reservations.values() if r.sku == sku)

    def available(self, sku: str) -> int:
        return self.on_hand(sku) - self.reserved(sku)

    def receive(self, sku: str, quantity: int) -> int:
        """Add delivered units; returns the new on-hand count."""
        if quantity <= 0:
            raise ValidationError(f"{sku}: received quantity must be positive")
        self._on_hand[sku] = self.on_hand(sku) + quantity
        return self._on_hand[sku]

    def set_stock(self, sku: str, quantity: int) -> None:
        """Set the counted on-hand quantity (stock take). It may not drop below what is reserved."""
        if quantity < 0:
            raise ValidationError(f"{sku}: stock cannot be negative")
        if quantity < self.reserved(sku):
            raise ValidationError(f"{sku}: {self.reserved(sku)} units are reserved, cannot set stock to {quantity}")
        self._on_hand[sku] = quantity

    def skus(self) -> list[str]:
        return sorted(self._on_hand)

    # reservations
    def reserve(self, order_id: str, sku: str, quantity: int) -> Reservation:
        if quantity <= 0:
            raise ValidationError(f"{sku}: reserved quantity must be positive")
        avail = self.available(sku)
        if quantity > avail:
            raise InsufficientStock(sku, quantity, avail)
        r = Reservation(f"R{self._next_id}", order_id, sku, quantity, self._clock())
        self._next_id += 1
        self._reservations[r.id] = r
        return r

    def reservations_for(self, order_id: str) -> list[Reservation]:
        return [r for r in self._reservations.values() if r.order_id == order_id]

    def release(self, order_id: str) -> int:
        """Drop every reservation of an order (it was cancelled); returns how many units were freed."""
        freed = 0
        for r in self.reservations_for(order_id):
            freed += r.quantity
            del self._reservations[r.id]
        return freed

    def commit(self, order_id: str) -> dict[str, int]:
        """The order shipped: its reserved units leave the warehouse. Returns {sku: units shipped}."""
        shipped: dict[str, int] = {}
        for r in self.reservations_for(order_id):
            self._on_hand[r.sku] = self.on_hand(r.sku) - r.quantity
            shipped[r.sku] = shipped.get(r.sku, 0) + r.quantity
            del self._reservations[r.id]
        if not shipped:
            raise ValidationError(f"order {order_id} has nothing reserved")
        return shipped

    def expire_reservations(self, max_age_s: float) -> list[str]:
        """Release reservations older than max_age_s; returns the affected order ids (sorted, no repeats)."""
        now = self._clock()
        old = [r for r in self._reservations.values() if now - r.created_at > max_age_s]
        for r in old:
            del self._reservations[r.id]
        return sorted({r.order_id for r in old})

    def restock(self, sku: str, quantity: int) -> None:
        """Returned goods go back on the shelf."""
        if quantity > 0:
            self._on_hand[sku] = self.on_hand(sku) + quantity

    def low_stock(self, threshold: int) -> list[tuple[str, int]]:
        """(sku, available) for SKUs whose available count is at or below the threshold, sorted by SKU."""
        return [(s, self.available(s)) for s in self.skus() if self.available(s) <= threshold]

    def valuation(self, catalog) -> Decimal:
        """On-hand units times catalog price, for SKUs in the catalog."""
        total = Decimal("0")
        for sku in self.skus():
            if sku in catalog:
                total += catalog.get(sku).price * self.on_hand(sku)
        return total

    def to_dict(self) -> dict:
        return {"on_hand": dict(self._on_hand), "reservations": [r.to_dict() for r in self._reservations.values()],
                "next_id": self._next_id}

    @classmethod
    def from_dict(cls, d: dict, clock=None) -> "Inventory":
        inv = cls(clock)
        inv._on_hand = {k: int(v) for k, v in d.get("on_hand", {}).items()}
        for x in d.get("reservations", []):
            r = Reservation(x["id"], x["order_id"], x["sku"], int(x["quantity"]), float(x["created_at"]))
            inv._reservations[r.id] = r
        inv._next_id = int(d.get("next_id", len(inv._reservations) + 1))
        return inv
