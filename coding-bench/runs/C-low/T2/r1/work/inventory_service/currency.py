"""Currency conversion and formatting. Rates are units of the currency per 1 USD."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import ValidationError
from .money import to_decimal

RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("151.30")}
DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


class UnsupportedCurrency(ValidationError):
    """A currency code that has no rate."""


def normalize(currency) -> str:
    """Return the upper-case currency code, accepting surrounding spaces."""
    code = str(currency).strip().upper()
    if code not in RATES:
        raise UnsupportedCurrency(f"unsupported currency {currency!r}")
    return code


def convert(amount_usd, currency) -> Decimal:
    """Convert a USD amount to `currency`, rounded half-up to that currency's decimals."""
    code = normalize(currency)
    q = Decimal(1).scaleb(-DECIMALS[code])
    return (to_decimal(amount_usd) * RATES[code]).quantize(q, rounding=ROUND_HALF_UP)


def format_amount(amount, currency) -> str:
    """Round `amount` to the currency's decimals and return it without a currency symbol."""
    code = normalize(currency)
    places = DECIMALS[code]
    q = Decimal(1).scaleb(-places)
    value = to_decimal(amount).quantize(q, rounding=ROUND_HALF_UP)
    return f"{value:.{places}f}"
