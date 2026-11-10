"""Order pricing: line discounts (bulk and category promotions), customer tier discounts, coupons, tax and shipping.

Order of the steps, each rounded half-up to the cent:
1. Each line's gross = unit price x quantity. A line gets the larger of the bulk discount (quantity >= 10) and its
   category promotion, never both.
2. The tier discount is a percentage of the merchandise after line discounts.
3. A coupon applies to what is left after the tier discount; it has a minimum, and a percent coupon may have a cap.
4. Tax is the region's rate on the amount after all discounts. Shipping is not taxed.
5. Shipping depends on the total weight, and is free from FREE_SHIPPING_FROM after all discounts (before tax).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

from .models import OrderLine, ValidationError
from .money import ZERO, percent_of, round_money, to_decimal

TIER_DISCOUNTS = {"standard": Decimal("0"), "silver": Decimal("5"), "gold": Decimal("10")}
BULK_THRESHOLD = 10
BULK_PERCENT = Decimal("5")
CATEGORY_PROMOS = {"garden": Decimal("15"), "lighting": Decimal("8")}
COUPONS = {
    "SAVE10": {"kind": "percent", "value": Decimal("10"), "min_subtotal": Decimal("50")},
    "FLAT5": {"kind": "fixed", "value": Decimal("5"), "min_subtotal": Decimal("20")},
    "BIG25": {"kind": "percent", "value": Decimal("25"), "min_subtotal": Decimal("200"), "max_discount": Decimal("100")},
}
TAX_RATES = {"US-CA": Decimal("7.25"), "US-NY": Decimal("8.875"), "US-OR": Decimal("0"), "DE": Decimal("19"),
             "JP": Decimal("10")}
FREE_SHIPPING_FROM = Decimal("100")


@dataclass
class PriceBreakdown:
    subtotal: Decimal
    line_discounts: Decimal
    tier_discount: Decimal
    coupon_discount: Decimal
    taxable: Decimal
    tax: Decimal
    shipping: Decimal
    total: Decimal
    lines: list[dict] = field(default_factory=list)

    @property
    def discount_total(self) -> Decimal:
        return self.line_discounts + self.tier_discount + self.coupon_discount

    def to_dict(self) -> dict[str, Decimal]:
        return {"subtotal": self.subtotal, "line_discounts": self.line_discounts, "tier_discount": self.tier_discount,
                "coupon_discount": self.coupon_discount, "taxable": self.taxable, "tax": self.tax,
                "shipping": self.shipping, "total": self.total}


def shipping_cost(weight_kg, discounted_subtotal) -> Decimal:
    """4.99 up to 1 kg, 9.99 up to 5 kg, then 1.50 per started kg above 5; free from FREE_SHIPPING_FROM."""
    if to_decimal(discounted_subtotal) >= FREE_SHIPPING_FROM:
        return ZERO
    w = to_decimal(weight_kg)
    if w <= 1:
        return Decimal("4.99")
    if w <= 5:
        return Decimal("9.99")
    extra = math.ceil(w - 5)
    return Decimal("9.99") + Decimal("1.50") * extra


def _check_preconditions(region, customer, lines):
    if region not in TAX_RATES:
        raise ValidationError(f"no tax rate for region {region!r}")
    if customer.tier not in TIER_DISCOUNTS:
        raise ValidationError(f"unknown customer tier {customer.tier!r}")
    if not lines:
        raise ValidationError("an order needs at least one line")


def _price_line(line, product) -> dict:
    """One line's gross, the larger of the bulk discount and the category promotion, and the net."""
    gross = round_money(line.unit_price * line.quantity)
    bulk = BULK_PERCENT if line.quantity >= BULK_THRESHOLD else ZERO
    promo = CATEGORY_PROMOS.get(product.category, ZERO)
    pct = max(bulk, promo)
    discount = round_money(percent_of(gross, pct))
    net = gross - discount
    return {"sku": line.sku, "quantity": line.quantity, "gross": gross, "discount": discount,
            "net": net, "percent": pct}


def _price_lines(lines: list[OrderLine], catalog):
    """Step 1: price every line, accumulating subtotal, line discounts and weight."""
    details = []
    subtotal = ZERO
    line_discounts = ZERO
    weight = ZERO
    for line in lines:
        if line.quantity <= 0:
            raise ValidationError(f"{line.sku}: quantity must be positive")
        product = catalog.get(line.sku)
        info = _price_line(line, product)
        details.append(info)
        subtotal += info["gross"]
        line_discounts += info["discount"]
        weight += product.weight_kg * line.quantity
    return details, subtotal, line_discounts, weight


def _apply_coupon(coupon, after_tier) -> Decimal:
    """Step 3: resolve the coupon against the amount left after the tier discount."""
    if not coupon:
        return ZERO
    code = coupon.strip().upper()
    rule = COUPONS.get(code)
    if rule is None:
        raise ValidationError(f"unknown coupon {coupon!r}")
    if after_tier < rule["min_subtotal"]:
        raise ValidationError(f"coupon {code} needs at least {rule['min_subtotal']} after discounts")
    if rule["kind"] == "percent":
        discount = round_money(percent_of(after_tier, rule["value"]))
        cap = rule.get("max_discount")
        if cap is not None and discount > cap:
            discount = cap
        return discount
    if rule["kind"] == "fixed":
        return min(rule["value"], after_tier)
    raise ValidationError(f"coupon {code} has an unknown kind")


def _finish(subtotal, line_discounts, tier_discount, coupon_discount, after_tier, region, weight,
            details) -> PriceBreakdown:
    """Steps 4-5: tax, shipping and the final total."""
    taxable = after_tier - coupon_discount
    tax = round_money(percent_of(taxable, TAX_RATES[region]))
    shipping = shipping_cost(weight, taxable)
    total = taxable + tax + shipping
    return PriceBreakdown(subtotal=subtotal, line_discounts=line_discounts, tier_discount=tier_discount,
                          coupon_discount=coupon_discount, taxable=taxable, tax=tax, shipping=shipping,
                          total=total, lines=details)


def compute_order_total(lines: list[OrderLine], catalog, customer, coupon: str | None = None,
                        region: str | None = None) -> PriceBreakdown:
    """Price an order. `lines` carry the unit price to charge; `catalog` gives each SKU's category and weight."""
    region = region or customer.region
    _check_preconditions(region, customer, lines)
    # 1. lines: gross, then the larger of the bulk discount and the category promotion
    details, subtotal, line_discounts, weight = _price_lines(lines, catalog)
    after_lines = subtotal - line_discounts
    # 2. customer tier
    tier_discount = round_money(percent_of(after_lines, TIER_DISCOUNTS[customer.tier]))
    after_tier = after_lines - tier_discount
    # 3. coupon, then 4. tax and 5. shipping
    coupon_discount = _apply_coupon(coupon, after_tier)
    return _finish(subtotal, line_discounts, tier_discount, coupon_discount, after_tier, region, weight, details)


def quote(catalog, customer, items: list[tuple[str, int]], coupon: str | None = None) -> PriceBreakdown:
    """Price (sku, quantity) pairs at today's catalog prices without creating an order."""
    lines = [OrderLine(sku, qty, catalog.get(sku).price) for sku, qty in items]
    return compute_order_total(lines, catalog, customer, coupon)
