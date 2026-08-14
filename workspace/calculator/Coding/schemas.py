"""Validated data models for calculator requests and results."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import math

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Operation(str, Enum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


class CalculationRequest(BaseModel):
    """A single, validated arithmetic request."""

    model_config = ConfigDict(extra="forbid")

    operation: Operation
    left: float
    right: float

    @field_validator("left", "right", mode="before")
    @classmethod
    def validate_operand(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("operands must be real numbers")
        if not math.isfinite(value):
            raise ValueError("operands must be finite")
        return value


class CalculationRecord(BaseModel):
    """An immutable calculation result stored in engine history."""

    model_config = ConfigDict(frozen=True)

    operation: Operation
    left: float
    right: float
    result: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
