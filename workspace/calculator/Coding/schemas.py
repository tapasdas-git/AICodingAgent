"""Validated configuration and history models for the calculator."""

from __future__ import annotations

from math import isfinite
from numbers import Rational, Real

from pydantic import BaseModel, ConfigDict, Field, field_validator


def require_finite_real(value: object, field_name: str) -> Real:
    """Validate a real number without replacing it with a coerced value."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")
    if not isinstance(value, Rational):
        try:
            finite = isfinite(value)
        except (OverflowError, TypeError, ValueError) as error:
            raise ValueError(f"{field_name} must be finite") from error
        if not finite:
            raise ValueError(f"{field_name} must be finite")
    return value


class CalculatorConfig(BaseModel):
    """Configuration accepted by :func:`create_calculator`."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")

    max_history: int = Field(default=100, ge=1)


class CalculationRecord(BaseModel):
    """Immutable record of one successful calculation."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    operation: str = Field(min_length=1)
    left: Real
    right: Real
    result: Real

    @field_validator("left", "right", "result")
    @classmethod
    def require_finite_number(cls, value: Real) -> Real:
        """Prevent invalid numeric state from entering calculation history."""

        return require_finite_real(value, "calculator value")
