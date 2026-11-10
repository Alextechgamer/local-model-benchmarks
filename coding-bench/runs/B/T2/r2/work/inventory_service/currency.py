"""Currency conversion and formatting.

Rates are units of the currency per 1 USD. A converted amount is the USD amount times the rate, rounded
half-up to the currency's number of decimals (two for USD, EUR and GBP; none for JPY). Currency codes are
case-insensitive and may have surrounding spaces.
"""
from __future__ import annotations

from decimal import Decimal

from .models import ValidationError
from .money import round_money, to_decimal

RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("151.30")}
DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


class UnsupportedCurrency(ValidationError):
    """A currency code that is not in RATES."""


def currency_code(currency) -> str:
    """The upper-case code; raises UnsupportedCurrency for codes not in RATES."""
    code = str(currency).strip().upper()
    if code not in RATES:
        raise UnsupportedCurrency(f"unsupported currency {currency!r}")
    return code


def convert(amount_usd, currency) -> Decimal:
    """`amount_usd` in the given currency: amount x rate, rounded half-up to the currency's decimals."""
    code = currency_code(currency)
    return round_money(to_decimal(amount_usd) * RATES[code], DECIMALS[code])


def format_amount(amount, currency) -> str:
    """Text for `amount` with the currency's number of decimals, e.g. '9.20' for EUR and '1867' for JPY."""
    code = currency_code(currency)
    places = DECIMALS[code]
    return f"{round_money(amount, places):.{places}f}"
