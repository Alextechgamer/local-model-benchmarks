"""Currency conversion and formatting for prices quoted outside the US.

Amounts in the pricing rules are always USD; a currency rate gives the units of that currency per 1 USD.
Currency codes are case-insensitive and may have surrounding spaces.
"""
from __future__ import annotations

from decimal import Decimal

from .models import ValidationError
from .money import round_money, to_decimal

RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("151.30")}
DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


class UnsupportedCurrency(ValidationError):
    """A currency code this program does not know."""


def normalize_currency(currency) -> str:
    code = str(currency).strip().upper()
    if code not in RATES:
        raise UnsupportedCurrency(f"unsupported currency {currency!r}")
    return code


def convert(amount_usd, currency) -> Decimal:
    """Convert a USD amount to `currency`, rounded half-up to that currency's decimals."""
    code = normalize_currency(currency)
    return round_money(to_decimal(amount_usd) * RATES[code], DECIMALS[code])


def format_amount(amount, currency) -> str:
    """Format an amount with the currency's number of decimals (e.g. '9.20' for EUR, '1867' for JPY)."""
    code = normalize_currency(currency)
    decimals = DECIMALS[code]
    rounded = round_money(to_decimal(amount), decimals)
    return f"{rounded:.{decimals}f}"
