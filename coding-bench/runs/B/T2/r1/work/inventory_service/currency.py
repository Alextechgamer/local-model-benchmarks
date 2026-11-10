"""Currency support: exchange rates, conversion and formatting for pricing in a currency other than USD.

RATES give the units of the currency per 1 USD. A USD amount is converted by multiplying with the rate and
rounding half-up to the currency's number of decimals (DECIMALS).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import ValidationError
from .money import to_decimal

RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("151.30")}
DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


class UnsupportedCurrency(ValidationError):
    """A currency code that is not in RATES."""


def normalize_currency(currency) -> str:
    """The upper-case code; codes are case-insensitive and may have surrounding spaces.

    Raises UnsupportedCurrency for a code that is not in RATES.
    """
    code = str(currency).strip().upper()
    if code not in RATES:
        raise UnsupportedCurrency(f"unsupported currency {currency!r}")
    return code


def convert(amount_usd, currency) -> Decimal:
    """`amount_usd` in the given currency: amount x rate, rounded half-up to the currency's decimals."""
    code = normalize_currency(currency)
    q = Decimal(1).scaleb(-DECIMALS[code])
    return (to_decimal(amount_usd) * RATES[code]).quantize(q, rounding=ROUND_HALF_UP)


def format_amount(amount, currency) -> str:
    """Text for an amount with the currency's number of decimals: '9.20' for EUR, '1867' for JPY."""
    code = normalize_currency(currency)
    q = Decimal(1).scaleb(-DECIMALS[code])
    return f"{to_decimal(amount).quantize(q, rounding=ROUND_HALF_UP):f}"
