import pytest

from inventory_service.catalog import Catalog
from inventory_service.inventory import Inventory
from inventory_service.models import Customer
from inventory_service.orders import OrderService

PRODUCTS = [
    ("TOO-0001", "Hammer", "12.50", "tools", "0.8"),
    ("TOO-0002", "Cordless Drill", "89.00", "tools", "1.9"),
    ("GAR-0001", "Garden Chair", "45.00", "garden", "4.5"),
    ("GAR-0002", "Hose 20m", "24.99", "garden", "2.2"),
    ("LIT-0001", "Desk Lamp", "32.00", "lighting", "1.1"),
    ("KIT-0001", "Mug", "6.50", "kitchen", "0.35"),
]
CUSTOMERS = [
    Customer("C1", "Ann", "standard", "US-CA"),
    Customer("C2", "Bob", "silver", "US-NY"),
    Customer("C3", "Cleo", "gold", "DE"),
    Customer("C4", "Dan", "standard", "US-OR"),
]


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def catalog():
    c = Catalog()
    for p in PRODUCTS:
        c.add_product(*p)
    return c


@pytest.fixture
def inventory(clock):
    inv = Inventory(clock)
    for p in PRODUCTS:
        inv.receive(p[0], 50)
    return inv


@pytest.fixture
def customers():
    return {c.id: Customer(c.id, c.name, c.tier, c.region) for c in CUSTOMERS}


@pytest.fixture
def svc(catalog, inventory, customers):
    return OrderService(catalog, inventory, customers)
