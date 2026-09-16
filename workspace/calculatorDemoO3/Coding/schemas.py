"""Validated request and result models for the calculator engine."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OperationType(str, Enum):
    """Arithmetic operations supported by the calculator engine."""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


class CalculationRequest(BaseModel):
    """A validated binary arithmetic calculation request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: OperationType
    operand1: Decimal = Field(allow_inf_nan=False)
    operand2: Decimal = Field(allow_inf_nan=False)


class CalculationResult(BaseModel):
    """The immutable result recorded for a successful calculation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: OperationType
    operand1: Decimal = Field(allow_inf_nan=False)
    operand2: Decimal = Field(allow_inf_nan=False)
    result: Decimal = Field(allow_inf_nan=False)
