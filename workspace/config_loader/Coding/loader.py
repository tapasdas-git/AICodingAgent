"""Pure configuration loading, parsing, and validation utilities."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar, get_args, get_origin

from pydantic import BaseModel, ValidationError

from errors import ConfigLoadError, ConfigValidationError
from schemas import AppConfig

try:  # pragma: no cover - the import path is validated by tests when available.
    import yaml
except Exception:  # pragma: no cover
    yaml = None


TConfig = TypeVar("TConfig", bound=BaseModel)
FileReader = Callable[[Path], str]


def _default_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_source_suffix(source: str | Path) -> str:
    return Path(source).suffix.lower()


def _parse_value(raw_value: str) -> Any:
    if not isinstance(raw_value, str):
        return raw_value

    try:
        return json.loads(raw_value)
    except Exception:
        return raw_value


def _set_nested_value(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for segment in path[:-1]:
        nested = current.get(segment)
        if not isinstance(nested, dict):
            nested = {}
            current[segment] = nested
        current = nested
    current[path[-1]] = value


def _resolve_model(annotation: Any) -> type[BaseModel] | None:
    origin = get_origin(annotation)
    if origin is None and isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    if origin is None:
        return None

    if origin is list or origin is dict:
        return None

    resolved_args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(resolved_args) == 1:
        return _resolve_model(resolved_args[0])
    return None


def _iter_model_paths(model_type: type[BaseModel], prefix: tuple[str, ...] = ()) -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for field_name, field_info in model_type.model_fields.items():
        path = prefix + (field_name,)
        paths.append(path)
        nested_model = _resolve_model(field_info.annotation)
        if nested_model is not None:
            paths.extend(_iter_model_paths(nested_model, path))
    return tuple(paths)


def _build_env_overrides(
    schema: type[TConfig],
    env: Mapping[str, str],
    env_prefix: str,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    prefix = f"{env_prefix.upper()}_"

    for path in _iter_model_paths(schema):
        env_key = prefix + "_".join(segment.upper() for segment in path)
        if env_key not in env:
            continue
        _set_nested_value(overrides, path, _parse_value(env[env_key]))

    return overrides


def _merge_dicts(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _parse_text(text: str, source: str | Path) -> dict[str, Any]:
    suffix = _normalize_source_suffix(source)

    if suffix == ".json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigLoadError(f"invalid JSON in {source}: {exc.msg}") from exc
    elif suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise ConfigLoadError("YAML support is unavailable because PyYAML is not installed")
        try:
            parsed = yaml.safe_load(text)
        except Exception as exc:  # pragma: no cover - exercised through valid/invalid parsing paths
            raise ConfigLoadError(f"invalid YAML in {source}: {exc}") from exc
    else:
        raise ConfigLoadError(f"unsupported configuration format for {source}")

    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ConfigLoadError("configuration root must be a mapping")
    return parsed


def validate_config(schema: type[TConfig], data: Mapping[str, Any]) -> TConfig:
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise ConfigValidationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ConfigLoader:
    """Load configuration files and apply deterministic environment overrides."""

    env: Mapping[str, str] = field(default_factory=lambda: os.environ)
    env_prefix: str = "APP"
    read_text: FileReader = _default_read_text

    def load(self, path: str | Path, schema: type[TConfig] = AppConfig) -> TConfig:
        file_path = Path(path)
        try:
            text = self.read_text(file_path)
        except OSError as exc:
            raise ConfigLoadError(f"unable to read configuration file {file_path}: {exc}") from exc
        return self.loads(text, source=file_path, schema=schema)

    def loads(self, text: str, *, source: str | Path, schema: type[TConfig] = AppConfig) -> TConfig:
        parsed = _parse_text(text, source)
        overrides = _build_env_overrides(schema, self.env, self.env_prefix)
        merged = _merge_dicts(parsed, overrides)
        return validate_config(schema, merged)


def load_config(
    path: str | Path,
    *,
    schema: type[TConfig] = AppConfig,
    env: Mapping[str, str] | None = None,
    env_prefix: str = "APP",
    read_text: FileReader | None = None,
) -> TConfig:
    """Load and validate a config file with optional dependency injection."""

    loader = ConfigLoader(
        env=os.environ if env is None else env,
        env_prefix=env_prefix,
        read_text=_default_read_text if read_text is None else read_text,
    )
    return loader.load(path, schema=schema)
