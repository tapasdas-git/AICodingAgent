"""Pydantic schemas for application configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatabaseConfig(_StrictBaseModel):
    host: str = Field(min_length=1)
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    database_name: str = Field(min_length=1)
    pool_size: int = Field(default=5, ge=1)
    connect_timeout_seconds: float = Field(default=30.0, gt=0.0)


class LoggingConfig(_StrictBaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s %(levelname)s %(name)s %(message)s"
    file_path: str | None = None

    @field_validator("level")
    @classmethod
    def _normalize_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in _LOG_LEVELS:
            raise ValueError(f"unsupported logging level: {value!r}")
        return normalized


class AppConfig(_StrictBaseModel):
    app_name: str = Field(min_length=1)
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    database: DatabaseConfig
    logging: LoggingConfig
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost"])

    @field_validator("allowed_hosts")
    @classmethod
    def _validate_allowed_hosts(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("allowed_hosts must not be empty")
        if any(not isinstance(host, str) or not host.strip() for host in value):
            raise ValueError("allowed_hosts must contain non-empty strings")
        return value
