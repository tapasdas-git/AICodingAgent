"""Validated request, reasoning, and classification schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Base model that rejects unexpected model-controlled fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TwitterCommentInput(StrictModel):
    """A single Twitter/X comment to classify."""

    text: str = Field(min_length=1, max_length=5_000)
    comment_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain visible content")
        return value


class ReasoningStep(StrictModel):
    """A concise, auditable risk signal rather than hidden chain of thought."""

    step: int = Field(ge=1, le=8)
    dimension: Literal["target", "harassment", "slur", "incitement", "context"]
    finding: str = Field(min_length=1, max_length=500)
    risk_score: float = Field(ge=0.0, le=1.0)


class ClassificationOutput(StrictModel):
    """Final structured risk assessment returned by the agent."""

    is_hate_speech: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1, max_length=2_000)
    category: Literal[
        "benign",
        "targeted_harassment",
        "slur",
        "incitement",
        "mixed",
        "error",
    ]

    @field_validator("category")
    @classmethod
    def category_matches_decision(cls, value: str, info: object) -> str:
        data = getattr(info, "data", {})
        decision = data.get("is_hate_speech")
        if decision is True and value in {"benign", "error"}:
            raise ValueError("hate-speech decisions require a risk category")
        if decision is False and value not in {"benign", "error"}:
            raise ValueError("non-hate-speech decisions require benign or error category")
        return value


class ReasoningResponse(StrictModel):
    """Internal validated response from the analysis pass."""

    steps: list[ReasoningStep] = Field(min_length=1, max_length=8)

    @field_validator("steps")
    @classmethod
    def require_ordered_unique_steps(cls, value: list[ReasoningStep]) -> list[ReasoningStep]:
        numbers = [item.step for item in value]
        if numbers != list(range(1, len(value) + 1)):
            raise ValueError("reasoning steps must be uniquely numbered from 1")
        return value
