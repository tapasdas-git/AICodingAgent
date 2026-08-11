"""File and environment loading helpers for configuration data."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import BaseModel, ValidationError

from .exceptions import (
    ConfigEnvironmentError,
    ConfigParseError,
    ConfigValidationError,
)
from .models import AppConfig

DEFAULT_ENV_PREFIX = "APP_CONFIG"
_NESTED_SEPARATOR = "__"


def load_config(
    path: str | Path,
    *,
    env: Mapping[str, str] | None = None,
    env_prefix: str = DEFAULT_ENV_PREFIX,
) -> AppConfig:
    """Load, override, and validate a configuration file."""

    return load_config_file(path, env=env, env_prefix=env_prefix)


def load_config_file(
    path: str | Path,
    *,
    env: Mapping[str, str] | None = None,
    env_prefix: str = DEFAULT_ENV_PREFIX,
) -> AppConfig:
    """Load and validate a configuration file from disk."""

    path = Path(path)
    raw_text = _read_text(path)
    parsed = _parse_document(raw_text, source=str(path), suffix=path.suffix.lower())
    return load_config_data(parsed, source=str(path), env=env, env_prefix=env_prefix)


def load_config_data(
    data: Mapping[str, Any],
    *,
    source: str = "<memory>",
    env: Mapping[str, str] | None = None,
    env_prefix: str = DEFAULT_ENV_PREFIX,
) -> AppConfig:
    """Validate an in-memory mapping and apply environment overrides."""

    if not isinstance(data, Mapping):
        raise ConfigParseError(f"{source}: configuration root must be a mapping")

    merged = copy.deepcopy(dict(data))
    if env:
        merged = apply_environment_overrides(
            merged,
            env=env,
            env_prefix=env_prefix,
            source=source,
        )

    try:
        return AppConfig.model_validate(merged)
    except ValidationError as exc:
        raise ConfigValidationError(f"{source}: invalid configuration data") from exc


def apply_environment_overrides(
    data: Mapping[str, Any],
    *,
    env: Mapping[str, str],
    env_prefix: str = DEFAULT_ENV_PREFIX,
    source: str = "<memory>",
) -> dict[str, Any]:
    """Merge prefixed environment overrides into configuration data."""

    if not env_prefix or _NESTED_SEPARATOR in env_prefix:
        raise ConfigEnvironmentError("env_prefix must be a simple non-empty prefix")

    normalized_prefix = env_prefix.upper() + "_"
    overrides: dict[str, Any] = {}
    for key, value in env.items():
        if not key.upper().startswith(normalized_prefix):
            continue
        suffix = key[len(normalized_prefix) :]
        if not suffix:
            raise ConfigEnvironmentError(f"{source}: malformed environment key {key!r}")
        parts = suffix.split(_NESTED_SEPARATOR)
        if any(not segment for segment in parts):
            raise ConfigEnvironmentError(f"{source}: malformed environment key {key!r}")
        _apply_single_override(overrides, AppConfig, parts, value, key, source)

    merged = copy.deepcopy(dict(data))
    _deep_merge(merged, overrides)
    return merged


def _apply_single_override(
    target: dict[str, Any],
    model_cls: type[AppConfig],
    parts: list[str],
    raw_value: str,
    env_key: str,
    source: str,
) -> None:
    current_model = model_cls
    current_target = target
    for index, part in enumerate(parts):
        field_name = _resolve_field_name(current_model, part)
        if field_name is None:
            joined = _NESTED_SEPARATOR.join(parts[: index + 1])
            raise ConfigEnvironmentError(
                f"{source}: unknown environment override path {env_key!r} ({joined!r})"
            )
        field = current_model.model_fields[field_name]
        if index == len(parts) - 1:
            current_target[field_name] = _parse_env_value(raw_value, env_key, source)
            return

        nested_model = _nested_model_type(field.annotation)
        if nested_model is None:
            raise ConfigEnvironmentError(
                f"{source}: environment key {env_key!r} targets non-nested field {field_name!r}"
            )

        existing = current_target.get(field_name)
        if existing is None:
            existing = {}
            current_target[field_name] = existing
        elif not isinstance(existing, dict):
            raise ConfigEnvironmentError(
                f"{source}: conflicting override for {env_key!r} on field {field_name!r}"
            )

        current_target = existing
        current_model = nested_model


def _deep_merge(target: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    for key, value in overrides.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, Mapping)
        ):
            _deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def _nested_model_type(annotation: Any) -> type[Any] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = getattr(annotation, "__origin__", None)
    if origin is None:
        return None
    for arg in getattr(annotation, "__args__", ()):
        nested = _nested_model_type(arg)
        if nested is not None:
            return nested
    return None


def _resolve_field_name(model_cls: type[Any], candidate: str) -> str | None:
    normalized = candidate.lower()
    for field_name in model_cls.model_fields:
        if field_name.lower() == normalized:
            return field_name
    return None


def _parse_env_value(raw_value: str, env_key: str, source: str) -> Any:
    if raw_value == "":
        return ""
    try:
        return yaml.safe_load(raw_value)
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigEnvironmentError(
            f"{source}: unable to parse environment value for {env_key!r}"
        ) from exc


def _parse_document(text: str, *, source: str, suffix: str) -> Mapping[str, Any]:
    if suffix == ".json":
        return _parse_json(text, source)
    if suffix in {".yaml", ".yml"}:
        return _parse_yaml(text, source)

    try:
        return _parse_json(text, source)
    except ConfigParseError:
        pass

    try:
        return _parse_yaml(text, source)
    except ConfigParseError as yaml_error:
        raise ConfigParseError(f"{source}: unable to parse as JSON or YAML") from yaml_error


def _parse_json(text: str, source: str) -> Mapping[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigParseError(f"{source}: invalid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise ConfigParseError(f"{source}: JSON root must be an object")
    return parsed


def _parse_yaml(text: str, source: str) -> Mapping[str, Any]:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigParseError(f"{source}: invalid YAML") from exc
    if not isinstance(parsed, Mapping):
        raise ConfigParseError(f"{source}: YAML root must be a mapping")
    return parsed


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigParseError(f"{path}: unable to read configuration file") from exc
