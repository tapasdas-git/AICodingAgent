"""Currency-rate lookup and conversion engine."""

from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Mapping, Protocol

from schemas import ConversionRequest, ConversionResult


class RateProvider(Protocol):
    """Boundary implemented by exchange-rate provider tools."""

    def get_rate(self, source_currency: str, target_currency: str) -> Decimal:
        """Return the multiplier from source currency to target currency."""


class MockExchangeRateProvider:
    """Offline rate provider using USD-denominated reference rates."""

    DEFAULT_USD_RATES: Mapping[str, Decimal] = {
        "USD": Decimal("1"),
        "INR": Decimal("83.00"),
        "EUR": Decimal("0.92"),
        "GBP": Decimal("0.79"),
    }

    def __init__(
        self,
        api_key: str,
        usd_rates: Mapping[str, Decimal] | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("EXCHANGE_API_KEY is required")
        self._api_key = api_key
        self._usd_rates = dict(usd_rates or self.DEFAULT_USD_RATES)

    def get_rate(self, source_currency: str, target_currency: str) -> Decimal:
        try:
            source_rate = self._usd_rates[source_currency]
            target_rate = self._usd_rates[target_currency]
        except KeyError as error:
            raise ValueError(f"rate unavailable for currency: {error.args[0]}") from error
        rate = target_rate / source_rate
        if rate <= 0:
            raise ValueError("exchange rate must be positive")
        return rate


class CurrencyConverter:
    """Validate requests and route rate lookup to an injected provider."""

    def __init__(self, rate_provider: RateProvider) -> None:
        self._rate_provider = rate_provider

    def convert(
        self, request: ConversionRequest | Mapping[str, object]
    ) -> ConversionResult:
        validated = (
            request
            if isinstance(request, ConversionRequest)
            else ConversionRequest.model_validate(request)
        )
        raw_rate = self._rate_provider.get_rate(
            validated.source_currency, validated.target_currency
        )
        rate = Decimal(str(raw_rate))
        if not rate.is_finite() or rate <= 0:
            raise ValueError("exchange rate must be a finite positive number")

        converted = (validated.amount * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return ConversionResult(
            source_currency=validated.source_currency,
            target_currency=validated.target_currency,
            source_amount=validated.amount,
            exchange_rate=rate,
            converted_amount=converted,
            formatted_amount=f"{validated.target_currency} {converted:,.2f}",
        )


def create_converter(
    rate_provider: RateProvider | None = None,
    *,
    getenv: Callable[[str], str | None] = os.getenv,
) -> CurrencyConverter:
    """Create the public conversion entry point without import-time side effects."""

    if rate_provider is None:
        rate_provider = MockExchangeRateProvider(getenv("EXCHANGE_API_KEY") or "")
    return CurrencyConverter(rate_provider)
