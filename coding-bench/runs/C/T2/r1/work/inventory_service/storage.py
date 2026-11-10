"""JSON persistence of the whole service state, with atomic writes and a migration from schema version 1.

Version 2 (current): prices and amounts are decimal strings ("12.30").
Version 1: product prices were integer cents under "price_cents"; there were no customer regions (all "US-CA").
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from decimal import Decimal

from .catalog import Catalog
from .inventory import Inventory
from .models import Customer, ValidationError
from .orders import OrderService

SCHEMA_VERSION = 2


@dataclass
class State:
    catalog: Catalog
    inventory: Inventory
    orders: OrderService


def new_state(clock=None) -> State:
    catalog, inventory = Catalog(), Inventory(clock)
    return State(catalog, inventory, OrderService(catalog, inventory))


def to_dict(state: State) -> dict:
    return {"version": SCHEMA_VERSION, "catalog": state.catalog.to_list(), "inventory": state.inventory.to_dict(),
            "customers": [c.to_dict() for c in state.orders.customers.values()], **state.orders.to_dict()}


def migrate(data: dict) -> dict:
    """Bring older files up to SCHEMA_VERSION. Returns a new dict; the input is not changed."""
    data = json.loads(json.dumps(data))
    version = data.get("version", 1)
    if version > SCHEMA_VERSION:
        raise ValidationError(f"state file version {version} is newer than this program ({SCHEMA_VERSION})")
    if version == 1:
        for p in data.get("catalog", []):
            if "price_cents" in p:
                p["price"] = str(Decimal(int(p.pop("price_cents"))) / 100)
        for c in data.get("customers", []):
            c.setdefault("region", "US-CA")
        data["version"] = 2
    return data


def from_dict(data: dict, clock=None) -> State:
    data = migrate(data)
    catalog = Catalog.from_list(data.get("catalog", []))
    inventory = Inventory.from_dict(data.get("inventory", {}), clock)
    orders = OrderService(catalog, inventory, {c["id"]: Customer.from_dict(c) for c in data.get("customers", [])})
    orders.load_orders(data)
    return State(catalog, inventory, orders)


def save(state: State, path: str) -> None:
    """Write the state as JSON. The file is replaced atomically, so a crash never leaves half a file."""
    text = json.dumps(to_dict(state), indent=1, sort_keys=True)
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load(path: str, clock=None) -> State:
    """Read a state file; a missing file gives an empty state."""
    if not os.path.exists(path):
        return new_state(clock)
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValidationError(f"{path} is not valid JSON: {e}") from None
    return from_dict(data, clock)
