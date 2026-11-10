"""Helpers for the hidden tests (they run with --noconftest, so no fixtures from the model's tree are used)."""
from decimal import Decimal as D

PRODUCTS = [
    ("TOO-0001", "Hammer", "12.50", "tools", "0.8"),
    ("TOO-0002", "Cordless Drill", "89.00", "tools", "1.9"),
    ("GAR-0001", "Garden Chair", "45.00", "garden", "4.5"),
    ("GAR-0002", "Hose 20m", "24.99", "garden", "2.2"),
    ("LIT-0001", "Desk Lamp", "32.00", "lighting", "1.1"),
    ("KIT-0001", "Mug", "6.50", "kitchen", "0.35"),
    ("KIT-0002", "Kettle", "39.90", "kitchen", "1.4"),
]
CUSTOMERS = [("C1", "Ann", "standard", "US-CA"), ("C2", "Bob", "silver", "US-NY"), ("C3", "Cleo", "gold", "DE"),
             ("C4", "Dan", "standard", "US-OR"), ("C5", "Eve", "gold", "US-CA"), ("C6", "Fay", "silver", "JP")]


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def world(stock=50):
    """(catalog, inventory, service, clock) with the products above, `stock` units each, and the customers."""
    from inventory_service.catalog import Catalog
    from inventory_service.inventory import Inventory
    from inventory_service.models import Customer
    from inventory_service.orders import OrderService
    clock = Clock()
    cat = Catalog()
    for p in PRODUCTS:
        cat.add_product(*p)
    inv = Inventory(clock)
    for p in PRODUCTS:
        inv.receive(p[0], stock)
    svc = OrderService(cat, inv, {c[0]: Customer(*c) for c in CUSTOMERS})
    return cat, inv, svc, clock


def customer(cid):
    from inventory_service.models import Customer
    return Customer(*next(c for c in CUSTOMERS if c[0] == cid))


def lines(cat, *items):
    from inventory_service.models import OrderLine
    return [OrderLine(s, q, cat.get(s).price) for s, q in items]
