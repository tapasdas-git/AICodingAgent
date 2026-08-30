"""Validated schemas returned by the string utility module."""

from pydantic import BaseModel, ConfigDict, Field


class StringMetrics(BaseModel):
    """Counts derived from a string.

    ``character_count`` includes whitespace and punctuation, while words are
    groups separated by Unicode whitespace.
    """

    model_config = ConfigDict(frozen=True)

    character_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    vowels_count: int = Field(ge=0)
