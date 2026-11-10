"""Money helpers. All amounts are Decimal; rounding is half-up to the cent unless stated otherwise."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0")


def to_decimal(value) -> Decimal:
    """Convert int, str or Decimal to Decimal. Floats go through str() so 0.1 stays 0.1."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not an amount")
    if isinstance(value, float):
        value = repr(value)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"not an amount: {value!r}") from e


def round_money(amount, places: int = 2) -> Decimal:
    """Round half-up to `places` decimals (2 = cents)."""
    q = Decimal(1).scaleb(-places)
    return to_decimal(amount).quantize(q, rounding=ROUND_HALF_UP)


def percent_of(amount, percent) -> Decimal:
    """`percent` percent of `amount`, not rounded."""
    return to_decimal(amount) * to_decimal(percent) / Decimal(100)


def money_str(amount) -> str:
    """'12.30' style text for an amount, rounded to cents."""
    return f"{round_money(amount):.2f}"


def split_evenly(amount, parts: int) -> list[Decimal]:
    """Split an amount into `parts` cent amounts that add up exactly; leftover cents go to the first parts."""
    if parts <= 0:
        raise ValueError("parts must be positive")
    total_cents = int(round_money(amount) / CENT)
    base, extra = divmod(total_cents, parts)
    return [(Decimal(base + (1 if i < extra else 0)) * CENT) for i in range(parts)]


def allocate_proportionally(amount, weights: list) -> list[Decimal]:
    """Split a cent amount over weights; shares are rounded down and leftover cents go to the largest remainders."""
    weights = [to_decimal(w) for w in weights]
    total_w = sum(weights, ZERO)
    total_cents = int(round_money(amount) / CENT)
    if total_w == 0:
        return [ZERO for _ in weights]
    raw = [Decimal(total_cents) * w / total_w for w in weights]
    floors = [int(r) for r in raw]
    left = total_cents - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:left]:
        floors[i] += 1
    return [Decimal(c) * CENT for c in floors]
