"""The product catalog: SKUs, prices, categories, weights and the active flag."""
from __future__ import annotations

import re
from decimal import Decimal

from .models import Product, ValidationError
from .money import to_decimal

SKU_RE = re.compile(r"^[A-Z]{3}-\d{4}$")


def normalize_category(category: str) -> str:
    """Categories are stored lower-case with single spaces: '  Garden  Tools ' -> 'garden tools'."""
    return " ".join(str(category).split()).lower()


class Catalog:
    def __init__(self):
        self._products: dict[str, Product] = {}

    def __len__(self) -> int:
        return len(self._products)

    def __contains__(self, sku: str) -> bool:
        return sku in self._products

    def add_product(self, sku: str, name: str, price, category: str, weight_kg="0") -> Product:
        """Add a new product. SKUs look like 'ABC-1234'; the price must be above zero."""
        sku = sku.strip().upper()
        if not SKU_RE.match(sku):
            raise ValidationError(f"bad SKU {sku!r}: expected three letters, a dash and four digits")
        if sku in self._products:
            raise ValidationError(f"SKU {sku} already exists")
        price = to_decimal(price)
        if price <= 0:
            raise ValidationError(f"{sku}: price must be above zero")
        weight = to_decimal(weight_kg)
        if weight < 0:
            raise ValidationError(f"{sku}: weight cannot be negative")
        if not name.strip():
            raise ValidationError(f"{sku}: name is empty")
        p = Product(sku, name.strip(), price, normalize_category(category), weight)
        self._products[sku] = p
        return p

    def get(self, sku: str) -> Product:
        try:
            return self._products[sku]
        except KeyError:
            raise ValidationError(f"unknown SKU {sku}") from None

    def update_price(self, sku: str, price) -> Product:
        p = self.get(sku)
        price = to_decimal(price)
        if price <= 0:
            raise ValidationError(f"{sku}: price must be above zero")
        p.price = price
        return p

    def update(self, sku: str, name: str, price, category: str, weight_kg="0") -> Product:
        """Replace every field of an existing product (used by the CSV import)."""
        p = self.get(sku)
        self.update_price(sku, price)
        p.name = name.strip()
        p.category = normalize_category(category)
        p.weight_kg = to_decimal(weight_kg)
        return p

    def deactivate(self, sku: str) -> None:
        self.get(sku).active = False

    def activate(self, sku: str) -> None:
        self.get(sku).active = True

    def products(self, include_inactive: bool = False) -> list[Product]:
        """Products sorted by SKU."""
        return [p for _, p in sorted(self._products.items()) if include_inactive or p.active]

    def search(self, text: str | None = None, category: str | None = None) -> list[Product]:
        """Active products whose name contains `text` (any case) and/or whose category matches."""
        out = []
        cat = normalize_category(category) if category else None
        for p in self.products():
            if text and text.lower() not in p.name.lower():
                continue
            if cat and p.category != cat:
                continue
            out.append(p)
        return out

    def categories(self) -> list[str]:
        return sorted({p.category for p in self.products()})

    def to_list(self) -> list[dict]:
        return [p.to_dict() for p in self.products(include_inactive=True)]

    @classmethod
    def from_list(cls, items: list[dict]) -> "Catalog":
        c = cls()
        for d in items:
            p = Product.from_dict(d)
            c._products[p.sku] = p
        return c
