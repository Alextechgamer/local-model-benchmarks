"""Currencies: conversion from USD and formatting with each currency's number of decimals."""
from __future__ import annotations

from decimal import Decimal

from .models import ValidationError
from .money import round_money, to_decimal

RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"), "JPY": Decimal("151.30")}
DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}


class UnsupportedCurrency(ValidationError):
    pass


def code_of(currency: str) -> str:
    code = str(currency).strip().upper()
    if code not in RATES:
        raise UnsupportedCurrency(f"unsupported currency {currency!r}")
    return code


def convert(amount_usd, currency) -> Decimal:
    """amount x rate, rounded half-up to the currency's decimals."""
    code = code_of(currency)
    return round_money(to_decimal(amount_usd) * RATES[code], DECIMALS[code])


def format_amount(amount, currency) -> str:
    code = code_of(currency)
    places = DECIMALS[code]
    return f"{round_money(amount, places):.{places}f}"
