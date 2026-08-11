"""Pydantic schemas for the configuration loader."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConfig(BaseModel):
    """Database connection settings."""

    model_config = ConfigDict(extra="forbid")

    host: str
    port: int = 5432
    username: str
    password: str
    database: str


class AppConfig(BaseModel):
    """Top-level application settings used by the tests."""

    model_config = ConfigDict(extra="forbid")

    name: str
    environment: Literal["development", "staging", "production"]
    debug: bool = False
    retries: int = 3
    allowed_hosts: list[str] = Field(default_factory=list)
    database: DatabaseConfig

