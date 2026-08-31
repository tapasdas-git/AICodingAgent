"""Validated data models for currency conversion requests and results."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
SUPPORTED_CURRENCIES = frozenset({"USD", "INR", "EUR", "GBP"})


class ConversionRequest(BaseModel):
    """A request to convert a positive amount between supported currencies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Decimal = Field(gt=0, allow_inf_nan=False)
    source_currency: CurrencyCode
    target_currency: CurrencyCode

    @field_validator("source_currency", "target_currency", mode="before")
    @classmethod
    def normalize_currency_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("source_currency", "target_currency")
    @classmethod
    def currency_must_be_supported(cls, value: str) -> str:
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError(f"unsupported currency: {value}")
        return value


class ConversionResult(BaseModel):
    """The deterministic result of a validated currency conversion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["success"] = "success"
    source_currency: CurrencyCode
    target_currency: CurrencyCode
    source_amount: Decimal = Field(gt=0, allow_inf_nan=False)
    exchange_rate: Decimal = Field(gt=0, allow_inf_nan=False)
    converted_amount: Decimal = Field(gt=0, allow_inf_nan=False)
    formatted_amount: str = Field(min_length=1)

    @field_validator("source_currency", "target_currency")
    @classmethod
    def currency_must_be_supported(cls, value: str) -> str:
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError(f"unsupported currency: {value}")
        return value
