"""Validated data models used by the calculator."""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Operation(str, Enum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


class CalculationRequest(BaseModel):
    """A validated binary arithmetic request."""

    model_config = ConfigDict(extra="forbid")

    operation: Operation
    left: float
    right: float

    @field_validator("left", "right", mode="before")
    @classmethod
    def validate_operand(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("operands must be real numbers")
        try:
            operand = float(value)
        except (OverflowError, ValueError) as exc:
            raise ValueError("operands must be representable as finite floats") from exc
        if not math.isfinite(operand):
            raise ValueError("operands must be finite")
        return operand


class CalculationRecord(BaseModel):
    """An immutable successful calculation stored in engine history."""

    model_config = ConfigDict(frozen=True)

    sequence: int = Field(ge=1)
    operation: Operation
    left: float
    right: float
    result: float


class CalculatorConfig(BaseModel):
    """Validated runtime configuration for a calculator instance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_history: int = Field(default=100, ge=1)
