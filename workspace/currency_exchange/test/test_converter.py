from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from converter import CurrencyConverter, MockExchangeRateProvider, create_converter
from schemas import ConversionRequest, ConversionResult


def test_conversion_routes_to_injected_offline_provider_and_formats_result():
    provider = Mock()
    provider.get_rate.return_value = Decimal("0.92")

    result = create_converter(provider).convert(
        {"amount": "100", "source_currency": " usd ", "target_currency": "eur"}
    )

    provider.get_rate.assert_called_once_with("USD", "EUR")
    assert result.status == "success"
    assert result == ConversionResult(
        source_currency="USD",
        target_currency="EUR",
        source_amount=Decimal("100"),
        exchange_rate=Decimal("0.92"),
        converted_amount=Decimal("92.00"),
        formatted_amount="EUR 92.00",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("source_currency", "CAD"), ("target_currency", "CAD"), ("status", "failed")],
)
def test_result_rejects_unsupported_currencies_and_invalid_status(field, value):
    data = {
        "status": "success",
        "source_currency": "USD",
        "target_currency": "EUR",
        "source_amount": "100",
        "exchange_rate": "0.92",
        "converted_amount": "92.00",
        "formatted_amount": "EUR 92.00",
    }
    data[field] = value
    with pytest.raises(ValidationError):
        ConversionResult.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [("source_currency", "CAD"), ("target_currency", "EURO")],
)
def test_request_rejects_unsupported_or_invalid_currency_codes(field, value):
    data = {"amount": "10", "source_currency": "USD", "target_currency": "GBP"}
    data[field] = value
    with pytest.raises(ValidationError):
        ConversionRequest.model_validate(data)


@pytest.mark.parametrize("amount", [0, -1, "NaN", "Infinity"])
def test_request_rejects_non_positive_or_non_finite_amount(amount):
    with pytest.raises(ValidationError):
        ConversionRequest(amount=amount, source_currency="USD", target_currency="INR")


def test_request_forbids_unexpected_input():
    with pytest.raises(ValidationError):
        ConversionRequest(
            amount=1, source_currency="USD", target_currency="INR", unexpected=True
        )


def test_mock_provider_calculates_cross_rate_and_same_currency_rate():
    provider = MockExchangeRateProvider("offline-test-key")
    assert provider.get_rate("EUR", "GBP") == Decimal("0.79") / Decimal("0.92")
    assert provider.get_rate("USD", "USD") == Decimal("1")


def test_mock_provider_rejects_missing_key_and_unknown_rate():
    with pytest.raises(ValueError, match="EXCHANGE_API_KEY"):
        MockExchangeRateProvider(" ")
    provider = MockExchangeRateProvider("offline-test-key")
    with pytest.raises(ValueError, match="rate unavailable"):
        provider.get_rate("CAD", "USD")


def test_factory_loads_api_key_dynamically_from_environment():
    with patch("converter.os.getenv", return_value="dynamic-test-key") as getenv:
        converter = create_converter(getenv=getenv)
    getenv.assert_called_once_with("EXCHANGE_API_KEY")
    assert converter.convert(
        ConversionRequest(amount="2", source_currency="USD", target_currency="INR")
    ).converted_amount == Decimal("166.00")


def test_factory_requires_api_key_for_default_provider():
    with pytest.raises(ValueError, match="EXCHANGE_API_KEY"):
        create_converter(getenv=lambda _: None)


@pytest.mark.parametrize("rate", [0, -1, "NaN", "Infinity"])
def test_converter_rejects_invalid_provider_observation(rate):
    provider = Mock()
    provider.get_rate.return_value = rate
    with pytest.raises(ValueError, match="finite positive"):
        CurrencyConverter(provider).convert(
            {"amount": 10, "source_currency": "USD", "target_currency": "GBP"}
        )
