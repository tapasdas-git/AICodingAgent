"""Pydantic schemas used by the configuration loader."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConfig(BaseModel):
    """Database connection settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(min_length=1, description="Database connection URL")
    pool_size: int = Field(default=5, ge=1, le=100, description="Maximum connections in the pool")
    connect_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        description="Timeout for establishing a database connection",
    )


class FeatureFlags(BaseModel):
    """Optional runtime switches."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    enable_cache: bool = False
    enable_metrics: bool = False


class AppConfig(BaseModel):
    """Top-level application configuration."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    service_name: str = Field(min_length=1, description="Human-readable application name")
    environment: Literal["dev", "test", "staging", "prod"] = "dev"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    database: DatabaseConfig
    features: FeatureFlags = Field(default_factory=FeatureFlags)

