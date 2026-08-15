"""Validated calculator configuration and result models."""

from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CalculatorConfig(BaseModel):
    """Configuration accepted by the calculator factory."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")

    max_history: int = Field(default=100, ge=1)


class CalculationRecord(BaseModel):
    """Immutable record of one successful calculation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: str = Field(min_length=1)
    left: float
    right: float
    result: float

    @field_validator("left", "right", "result")
    @classmethod
    def validate_finite_number(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("calculator values must be finite")
        return value
