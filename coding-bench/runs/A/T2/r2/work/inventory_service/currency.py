"""Currency codes, rates, decimals, and conversion/formatting of amounts.

`RATES` are units of the currency per 1 USD. Conversions round half-up to the currency's number of decimals.
"""
from __future__ import annotations

from decimal import Decimal

from .models import ValidationError
from .money import round_money, to_decimal

RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("151.30")}
DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


class UnsupportedCurrency(ValidationError):
    """Raised for an unknown currency code."""


def code(currency) -> str:
    """The upper-case code for a currency name: ' eur ' -> 'EUR'."""
    return str(currency).strip().upper()


def convert(amount_usd, currency: str) -> Decimal:
    """`amount_usd` (in USD) converted to `currency`, rounded half-up to its number of decimals."""
    c = code(currency)
    if c not in RATES:
        raise UnsupportedCurrency(f"unsupported currency {currency!r}")
    return round_money(to_decimal(amount_usd) * RATES[c], DECIMALS[c])


def format_amount(amount, currency: str) -> str:
    """`amount` shown with the currency's number of decimals, e.g. '9.20' (EUR) or '1867' (JPY)."""
    c = code(currency)
    if c not in DECIMALS:
        raise UnsupportedCurrency(f"unsupported currency {currency!r}")
    return f"{round_money(amount, DECIMALS[c]):.{DECIMALS[c]}f}"
