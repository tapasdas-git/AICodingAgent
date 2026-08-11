"""Pure-Python configuration loading and environment override support."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Generic, Mapping, TypeVar, get_args, get_origin

import yaml
from pydantic import BaseModel, ValidationError

from .exceptions import ConfigFileError, ConfigValidationError, EnvironmentOverrideError

T = TypeVar("T", bound=BaseModel)


def _decode_env_value(value: str) -> Any:
    """Decode common environment value representations deterministically."""

    text = value.strip()
    if text == "":
        return ""

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _model_type(annotation: Any) -> type[BaseModel] | None:
    """Resolve a nested BaseModel type from an annotation if one exists."""

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation

    origin = get_origin(annotation)
    if origin is None:
        return None

    for candidate in get_args(annotation):
        nested = _model_type(candidate)
        if nested is not None:
            return nested
    return None


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


_MISSING = object()


class ConfigLoader(Generic[T]):
    """Load and validate configuration files with env var overrides."""

    def __init__(
        self,
        schema: type[T],
        *,
        env: Mapping[str, str] | None = None,
        env_prefix: str = "APP_",
        file_reader: Callable[[Path], str] | None = None,
    ) -> None:
        if not isinstance(schema, type) or not issubclass(schema, BaseModel):
            raise TypeError("schema must be a Pydantic BaseModel subclass")
        if not env_prefix:
            raise ValueError("env_prefix must not be empty")

        self._schema = schema
        self._env = dict(os.environ if env is None else env)
        self._env_prefix = env_prefix
        self._file_reader = file_reader or self._default_file_reader

    @staticmethod
    def _default_file_reader(path: Path) -> str:
        if not path.is_file():
            raise ConfigFileError(f"configuration file does not exist: {path}")
        return path.read_text(encoding="utf-8")

    def load(self, path: str | Path) -> T:
        """Load configuration from a YAML or JSON file."""

        config_path = Path(path)

        raw_data = self._parse_file(config_path)
        overrides = self._collect_env_overrides()
        merged = _deep_merge(raw_data, overrides)

        try:
            return self._schema.model_validate(merged)
        except ValidationError as exc:
            raise ConfigValidationError(str(exc)) from exc

    def _parse_file(self, path: Path) -> dict[str, Any]:
        text = self._file_reader(path)
        suffix = path.suffix.lower()

        try:
            if suffix in {".yaml", ".yml"}:
                parsed = yaml.safe_load(text) or {}
            elif suffix == ".json":
                parsed = json.loads(text) if text.strip() else {}
            else:
                raise ConfigFileError(
                    f"unsupported configuration format for {path.name}"
                )
        except (yaml.YAMLError, json.JSONDecodeError) as exc:
            raise ConfigFileError(f"failed to parse configuration file {path}") from exc

        if not isinstance(parsed, dict):
            raise ConfigFileError("top-level configuration data must be a mapping")
        return parsed

    def _collect_env_overrides(self) -> dict[str, Any]:
        overrides: dict[str, Any] = {}
        for key, value in self._env.items():
            if not key.upper().startswith(self._env_prefix.upper()):
                continue

            suffix = key[len(self._env_prefix) :]
            if not suffix:
                raise EnvironmentOverrideError("environment override name is empty")

            parts = [part.lower() for part in suffix.split("__")]
            if any(part == "" for part in parts):
                raise EnvironmentOverrideError(f"invalid override path in {key}")

            self._validate_override_path(parts, key)
            self._insert_override(overrides, parts, _decode_env_value(value), key)

        return overrides

    def _insert_override(
        self, overrides: dict[str, Any], parts: list[str], value: Any, key: str
    ) -> None:
        current = overrides
        for part in parts[:-1]:
            existing = current.get(part, _MISSING)
            if existing is _MISSING:
                next_node: dict[str, Any] = {}
                current[part] = next_node
                current = next_node
                continue

            if not isinstance(existing, dict):
                raise EnvironmentOverrideError(
                    f"conflicting environment overrides for '{key}' at '{part}'"
                )
            current = existing

        leaf = parts[-1]
        existing = current.get(leaf, _MISSING)
        if existing is not _MISSING:
            raise EnvironmentOverrideError(
                f"conflicting environment overrides for '{key}' at '{leaf}'"
            )

        current[leaf] = value

    def _validate_override_path(self, parts: list[str], key: str) -> None:
        model: type[BaseModel] = self._schema
        for index, part in enumerate(parts):
            field = model.model_fields.get(part)
            if field is None:
                raise EnvironmentOverrideError(
                    f"unknown configuration override '{key}' for field '{part}'"
                )

            is_leaf = index == len(parts) - 1
            nested = _model_type(field.annotation)
            if not is_leaf:
                if nested is None:
                    raise EnvironmentOverrideError(
                        f"override '{key}' tries to descend into non-model field '{part}'"
                    )
                model = nested


def load_config(
    path: str | Path,
    schema: type[T],
    *,
    env: Mapping[str, str] | None = None,
    env_prefix: str = "APP_",
    file_reader: Callable[[Path], str] | None = None,
) -> T:
    """Convenience wrapper that builds a loader and returns validated config."""

    return ConfigLoader(
        schema,
        env=env,
        env_prefix=env_prefix,
        file_reader=file_reader,
    ).load(path)
