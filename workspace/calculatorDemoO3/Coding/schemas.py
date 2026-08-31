"""Validated data models for calculator requests and results."""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class OperationType(str, Enum):
    """Operations supported by the calculator engine."""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


class CalculationRequest(BaseModel):
    """A validated binary arithmetic request."""

    model_config = ConfigDict(strict=True, frozen=True, allow_inf_nan=False)

    operation: OperationType
    operand1: float
    operand2: float


class CalculationResult(BaseModel):
    """The validated output of a calculation."""

    model_config = ConfigDict(strict=True, frozen=True, allow_inf_nan=False)

    operation: OperationType
    operand1: float
    operand2: float
    result: float
