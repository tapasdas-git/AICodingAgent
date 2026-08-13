"""Load YAML/JSON files, apply environment overrides, and validate them."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from schemas import LoaderSettings

ConfigModel = TypeVar("ConfigModel", bound=BaseModel)


class ConfigLoadError(ValueError):
    """Raised when a configuration file cannot be safely loaded."""


class ConfigLoader:
    """A reusable loader with validated, immutable settings."""

    def __init__(self, settings: LoaderSettings) -> None:
        self._settings = settings

    def load(
        self,
        path: str | os.PathLike[str],
        schema: type[ConfigModel],
        *,
        environ: Mapping[str, str] | None = None,
    ) -> ConfigModel:
        """Return validated configuration, with matching env values winning."""
        if not isinstance(schema, type) or not issubclass(schema, BaseModel):
            raise TypeError("schema must be a Pydantic BaseModel class")

        config_path = Path(path)
        data = self._read_mapping(config_path)
        merged = self._apply_environment(data, os.environ if environ is None else environ)
        return schema.model_validate(merged)

    def _read_mapping(self, path: Path) -> dict[str, Any]:
        suffix = path.suffix.casefold()
        if suffix not in {".json", ".yaml", ".yml"}:
            raise ConfigLoadError(
                f"unsupported configuration format {path.suffix!r}; use JSON or YAML"
            )
        try:
            text = path.read_text(encoding=self._settings.encoding)
        except (OSError, UnicodeError) as exc:
            raise ConfigLoadError(f"unable to read configuration file: {path}") from exc

        try:
            parsed = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise ConfigLoadError(f"invalid {suffix.lstrip('.').upper()} configuration") from exc

        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ConfigLoadError("configuration root must be an object/mapping")
        self._validate_mapping_keys(parsed)
        return parsed

    @classmethod
    def _validate_mapping_keys(cls, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested_value in value.items():
                if not isinstance(key, str):
                    raise ConfigLoadError("configuration mapping keys must be strings")
                cls._validate_mapping_keys(nested_value)
        elif isinstance(value, list):
            for item in value:
                cls._validate_mapping_keys(item)

    def _apply_environment(
        self, data: dict[str, Any], environ: Mapping[str, str]
    ) -> dict[str, Any]:
        result = deepcopy(data)
        prefix = self._settings.env_prefix
        delimiter = self._settings.env_nested_delimiter

        for name in sorted(environ):
            if not name.startswith(prefix):
                continue
            raw_path = name[len(prefix) :]
            parts = raw_path.split(delimiter)
            if not raw_path or any(not part for part in parts):
                raise ConfigLoadError(f"invalid environment override name: {name}")
            self._set_nested(result, [part.casefold() for part in parts], environ[name], name)
        return result

    @staticmethod
    def _set_nested(
        target: dict[str, Any], parts: list[str], value: str, env_name: str
    ) -> None:
        current = target
        for part in parts[:-1]:
            matching_key = next((key for key in current if key.casefold() == part), part)
            existing = current.get(matching_key)
            if existing is None:
                nested: dict[str, Any] = {}
                current[matching_key] = nested
                current = nested
            elif isinstance(existing, dict):
                current = existing
            else:
                raise ConfigLoadError(
                    f"environment override {env_name} conflicts with a scalar value"
                )
        leaf = parts[-1]
        matching_leaf = next((key for key in current if key.casefold() == leaf), leaf)
        current[matching_leaf] = value


def create_config_loader(
    settings: LoaderSettings | Mapping[str, Any] | None = None,
) -> ConfigLoader:
    """Public factory for a loader; dependencies stay injectable and offline."""
    if settings is None:
        validated = LoaderSettings()
    elif isinstance(settings, LoaderSettings):
        validated = settings
    elif isinstance(settings, Mapping):
        validated = LoaderSettings.model_validate(dict(settings))
    else:
        raise TypeError("settings must be LoaderSettings, a mapping, or None")
    return ConfigLoader(validated)
