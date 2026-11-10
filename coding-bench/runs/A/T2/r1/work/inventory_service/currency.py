"""Multi-currency display of amounts. Every pricing rule stays a USD amount; only results are converted.

A rate is how many units of the currency buy 1 USD, so a USD amount times the rate is the same amount in that
currency, rounded half-up to the currency's number of decimals (JPY has none).
"""
from __future__ import annotations

from decimal import Decimal

from .models import ValidationError
from .money import round_money, to_decimal

RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("151.30")}
DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


class UnsupportedCurrency(ValidationError):
    """An unknown currency code."""


def currency_code(currency) -> str:
    """The upper-case code for `currency`, which may be lower case and have surrounding spaces."""
    code = str(currency).strip().upper()
    if code not in RATES:
        raise UnsupportedCurrency(f"unknown currency {currency!r}")
    return code


def convert(amount_usd, currency) -> Decimal:
    """`amount_usd` in USD as `currency`: times the rate, rounded half-up to the currency's decimals."""
    code = currency_code(currency)
    return round_money(to_decimal(amount_usd) * RATES[code], DECIMALS[code])


def format_amount(amount, currency) -> str:
    """`amount` as text with the currency's number of decimals, e.g. "9.20" for EUR and "1867" for JPY."""
    code = currency_code(currency)
    places = DECIMALS[code]
    return f"{round_money(amount, places):.{places}f}"
