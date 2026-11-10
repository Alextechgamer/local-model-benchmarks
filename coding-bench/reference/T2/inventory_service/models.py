"""Data classes shared by the package, with dict round-tripping for JSON storage."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .money import to_decimal

ORDER_STATUSES = ("reserved", "shipped", "cancelled", "partially_refunded", "refunded")
CUSTOMER_TIERS = ("standard", "silver", "gold")


class ValidationError(ValueError):
    """Bad input from a caller (unknown SKU, bad quantity, wrong order state, ...)."""


@dataclass
class Product:
    sku: str
    name: str
    price: Decimal
    category: str
    weight_kg: Decimal = Decimal("0")
    active: bool = True

    def to_dict(self) -> dict:
        return {"sku": self.sku, "name": self.name, "price": str(self.price), "category": self.category,
                "weight_kg": str(self.weight_kg), "active": self.active}

    @classmethod
    def from_dict(cls, d: dict) -> "Product":
        return cls(d["sku"], d["name"], to_decimal(d["price"]), d["category"], to_decimal(d.get("weight_kg", "0")),
                   bool(d.get("active", True)))


@dataclass
class Customer:
    id: str
    name: str
    tier: str = "standard"
    region: str = "US-CA"

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "tier": self.tier, "region": self.region}

    @classmethod
    def from_dict(cls, d: dict) -> "Customer":
        return cls(d["id"], d["name"], d.get("tier", "standard"), d.get("region", "US-CA"))


@dataclass
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal

    def gross(self) -> Decimal:
        return self.unit_price * self.quantity

    def to_dict(self) -> dict:
        return {"sku": self.sku, "quantity": self.quantity, "unit_price": str(self.unit_price)}

    @classmethod
    def from_dict(cls, d: dict) -> "OrderLine":
        return cls(d["sku"], int(d["quantity"]), to_decimal(d["unit_price"]))


@dataclass
class Refund:
    id: str
    order_id: str
    quantities: dict[str, int]
    amount: Decimal
    restocked: bool

    def to_dict(self) -> dict:
        return {"id": self.id, "order_id": self.order_id, "quantities": dict(self.quantities),
                "amount": str(self.amount), "restocked": self.restocked}

    @classmethod
    def from_dict(cls, d: dict) -> "Refund":
        return cls(d["id"], d["order_id"], {k: int(v) for k, v in d["quantities"].items()}, to_decimal(d["amount"]),
                   bool(d["restocked"]))


@dataclass
class Order:
    id: str
    customer_id: str
    lines: list[OrderLine]
    region: str
    coupon: str | None = None
    status: str = "reserved"
    totals: dict[str, Decimal] = field(default_factory=dict)
    refunds: list[Refund] = field(default_factory=list)
    currency: str = "USD"

    def quantity_of(self, sku: str) -> int:
        return sum(l.quantity for l in self.lines if l.sku == sku)

    def refunded_quantity(self, sku: str) -> int:
        return sum(r.quantities.get(sku, 0) for r in self.refunds)

    def refunded_amount(self) -> Decimal:
        return sum((r.amount for r in self.refunds), Decimal("0"))

    def to_dict(self) -> dict:
        return {"id": self.id, "customer_id": self.customer_id, "lines": [l.to_dict() for l in self.lines],
                "region": self.region, "coupon": self.coupon, "status": self.status,
                "totals": {k: str(v) for k, v in self.totals.items()}, "refunds": [r.to_dict() for r in self.refunds], "currency": self.currency}

    @classmethod
    def from_dict(cls, d: dict) -> "Order":
        return cls(d["id"], d["customer_id"], [OrderLine.from_dict(x) for x in d["lines"]], d["region"],
                   d.get("coupon"), d.get("status", "reserved"),
                   {k: to_decimal(v) for k, v in d.get("totals", {}).items()},
                   [Refund.from_dict(x) for x in d.get("refunds", [])], d.get("currency", "USD"))
