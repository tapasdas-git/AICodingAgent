"""Validated data models for the calculator engine."""

from __future__ import annotations

import math
from enum import Enum
from numbers import Number
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OperationName(str, Enum):
    """Names of the operations included with the standard calculator."""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


def _finite_number(value: Any) -> float:
    """Convert a real numeric value to a finite float without accepting booleans."""

    if isinstance(value, bool) or not isinstance(value, Number) or isinstance(value, complex):
        raise ValueError("operands must be real numbers")
    try:
        converted = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("operands must be finite real numbers") from exc
    if not math.isfinite(converted):
        raise ValueError("operands must be finite real numbers")
    return converted


class CalculatorConfig(BaseModel):
    """Validated runtime configuration for a calculator engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    history_limit: int | None = Field(default=None, ge=1)


class CalculationRequest(BaseModel):
    """A validated request to execute one binary operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: str = Field(min_length=1)
    left: float
    right: float

    @field_validator("operation")
    @classmethod
    def _normalize_operation(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("operation must not be empty")
        return normalized

    @field_validator("left", "right", mode="before")
    @classmethod
    def _validate_operand(cls, value: Any) -> float:
        return _finite_number(value)


class CalculationRecord(BaseModel):
    """An immutable successful calculation stored in engine history."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    operation: str = Field(min_length=1)
    left: float
    right: float
    result: float

    @field_validator("left", "right", "result", mode="before")
    @classmethod
    def _validate_number(cls, value: Any) -> float:
        return _finite_number(value)
