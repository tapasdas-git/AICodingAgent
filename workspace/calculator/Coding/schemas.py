"""Validated request and result models for calculator operations."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Operation(str, Enum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    POWER = "power"


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Operation
    left: float = Field(strict=True, allow_inf_nan=False)
    right: float = Field(strict=True, allow_inf_nan=False)


class CalculationRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: Operation
    left: float = Field(allow_inf_nan=False)
    right: float = Field(allow_inf_nan=False)
    result: float = Field(allow_inf_nan=False)
