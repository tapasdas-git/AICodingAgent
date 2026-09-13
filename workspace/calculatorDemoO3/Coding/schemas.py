"""Validated request and result models for the calculator engine."""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class OperationType(str, Enum):
    """Arithmetic operations supported by :class:`CalculatorEngine`."""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


class CalculationRequest(BaseModel):
    """A validated request for one binary arithmetic operation."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    operation: OperationType
    operand1: float
    operand2: float


class CalculationResult(BaseModel):
    """An immutable record of a successful calculation."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    operation: OperationType
    operand1: float
    operand2: float
    result: float
