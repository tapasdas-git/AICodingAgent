"""Validated request and result schemas for calculator operations."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OperationType(str, Enum):
    """Operations supported by the standard calculator factory."""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


class CalculationRequest(BaseModel):
    """A validated binary arithmetic request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: OperationType
    operand1: float = Field(strict=True, allow_inf_nan=False)
    operand2: float = Field(strict=True, allow_inf_nan=False)


class CalculationResult(BaseModel):
    """The immutable record stored after a successful calculation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: OperationType
    operand1: float = Field(strict=True, allow_inf_nan=False)
    operand2: float = Field(strict=True, allow_inf_nan=False)
    result: float = Field(strict=True, allow_inf_nan=False)
