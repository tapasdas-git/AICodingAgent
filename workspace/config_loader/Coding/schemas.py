"""Validated configuration for the config loader itself."""

from __future__ import annotations

import codecs

from pydantic import BaseModel, ConfigDict, field_validator


class LoaderSettings(BaseModel):
    """Controls file loading and environment-variable overrides."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    env_prefix: str = "APP_"
    env_nested_delimiter: str = "__"
    encoding: str = "utf-8"

    @field_validator("env_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("env_prefix must not be empty")
        if "=" in value or "\x00" in value:
            raise ValueError("env_prefix contains invalid characters")
        return value

    @field_validator("env_nested_delimiter")
    @classmethod
    def validate_delimiter(cls, value: str) -> str:
        if not value or value.isspace():
            raise ValueError("env_nested_delimiter must not be empty")
        if "=" in value or "\x00" in value:
            raise ValueError("env_nested_delimiter contains invalid characters")
        return value

    @field_validator("encoding")
    @classmethod
    def validate_encoding(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("encoding must not be empty")
        try:
            codecs.lookup(value)
        except LookupError as exc:
            raise ValueError("encoding must name a registered codec") from exc
        return value
