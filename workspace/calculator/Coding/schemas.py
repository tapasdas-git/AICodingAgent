"""Validated calculator configuration and history models."""

from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CalculatorConfig(BaseModel):
    """Validated configuration for a calculator instance."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")

    max_history: int = Field(default=100, strict=True, ge=1)


class CalculationRecord(BaseModel):
    """Immutable record of one successful calculation."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    operation: str = Field(min_length=1)
    left: int | float
    right: int | float
    result: int | float

    @field_validator("left", "right", "result")
    @classmethod
    def require_finite_number(cls, value: int | float) -> int | float:
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("calculator values must be finite")
        return value
