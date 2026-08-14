"""Validated request and history models for calculator operations."""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


def is_finite_number(value: object) -> bool:
    """Return whether value is a supported finite number without coercing integers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return True if isinstance(value, int) else math.isfinite(value)


class Operation(str, Enum):
    """Operations supported by the standard calculator."""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


class CalculationRequest(BaseModel):
    """A validated binary arithmetic request."""

    model_config = ConfigDict(strict=True, frozen=True)

    operation: Operation
    left: int | float
    right: int | float

    @field_validator("operation", mode="before")
    @classmethod
    def validate_operation(cls, value: object) -> Operation:
        if isinstance(value, Operation):
            return value
        if isinstance(value, str):
            try:
                return Operation(value)
            except ValueError as error:
                raise ValueError(f"unsupported operation: {value}") from error
        raise ValueError("operation must be a supported operation name")

    @field_validator("left", "right", mode="before")
    @classmethod
    def validate_operand(cls, value: object) -> int | float:
        if not is_finite_number(value):
            raise ValueError("operands must be finite numbers")
        return value


class CalculationRecord(BaseModel):
    """One successful calculation stored in engine history."""

    model_config = ConfigDict(strict=True, frozen=True)

    operation: Operation
    left: int | float
    right: int | float
    result: int | float
