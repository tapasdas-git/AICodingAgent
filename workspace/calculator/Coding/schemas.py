from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

OperationName = Literal["add", "subtract", "multiply", "divide", "power"]


class CalculationRequest(BaseModel):
    """Validated input for one calculator operation."""

    model_config = ConfigDict(strict=True)

    operation: OperationName
    left: float
    right: float

    @field_validator("left", "right")
    @classmethod
    def validate_finite_number(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("operands must be finite numbers")
        return value


class CalculationRecord(BaseModel):
    """Immutable history entry produced after a successful calculation."""

    model_config = ConfigDict(frozen=True)

    operation: OperationName
    left: float
    right: float
    result: float

