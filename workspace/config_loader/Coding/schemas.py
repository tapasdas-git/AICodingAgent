"""Pydantic schemas for configuration loading and validation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConfig(BaseModel):
    """Database-specific configuration."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(..., min_length=1)
    pool_size: int = Field(default=5, ge=1)
    echo: bool = False


class LoggingConfig(BaseModel):
    """Logging-related configuration."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: str = "%(levelname)s:%(name)s:%(message)s"


class ConfigSettings(BaseModel):
    """Application configuration loaded from YAML or JSON."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    app_name: str = Field(..., min_length=1)
    debug: bool = False
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    retries: int = Field(default=3, ge=0)
    timeout_seconds: float = Field(default=30.0, gt=0)
    tags: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(default_factory=list)
    database: DatabaseConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

