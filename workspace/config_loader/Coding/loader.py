"""Configuration file loader with environment variable overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any, Callable, Generic, Mapping, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel

from .schemas import ConfigSettings

TConfig = TypeVar("TConfig", bound=BaseModel)


def _load_yaml_text(text: str) -> Any:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency issue only
        raise RuntimeError("PyYAML is required to load YAML configuration files") from exc

    return yaml.safe_load(text)


def _parse_bool(raw_value: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {raw_value!r}")


def _unwrap_annotation(annotation: Any) -> Any:
    while True:
        origin = get_origin(annotation)
        if origin is None:
            return annotation
        if origin is Annotated:
            annotation = get_args(annotation)[0]
            continue
        if origin in {Union, getattr(__import__("types"), "UnionType", Union)}:
            non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
            if len(non_none) == 1:
                annotation = non_none[0]
                continue
        return annotation


def _coerce_value(raw_value: str, annotation: Any) -> Any:
    annotation = _unwrap_annotation(annotation)
    origin = get_origin(annotation)

    if origin is list:
        inner_type = get_args(annotation)[0] if get_args(annotation) else Any
        stripped = raw_value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            parsed = json.loads(stripped)
            if not isinstance(parsed, list):
                raise ValueError("List override must decode to a JSON array")
            return [_coerce_json_item(item, inner_type) for item in parsed]
        return [_coerce_value(part.strip(), inner_type) for part in raw_value.split(",") if part.strip()]

    if origin is dict:
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError("Dictionary override must decode to a JSON object")
        return parsed

    if annotation is bool:
        return _parse_bool(raw_value)
    if annotation is int:
        return int(raw_value)
    if annotation is float:
        return float(raw_value)
    if annotation is str:
        return raw_value
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError("Model override must decode to a JSON object")
        return parsed

    return raw_value


def _coerce_json_item(value: Any, annotation: Any) -> Any:
    annotation = _unwrap_annotation(annotation)
    origin = get_origin(annotation)
    if origin is list:
        inner_type = get_args(annotation)[0] if get_args(annotation) else Any
        if not isinstance(value, list):
            raise ValueError("Nested list override must be a list")
        return [_coerce_json_item(item, inner_type) for item in value]
    if annotation is bool:
        return bool(value) if isinstance(value, bool) else _parse_bool(str(value))
    if annotation is int:
        return int(value)
    if annotation is float:
        return float(value)
    if annotation is str:
        return str(value)
    return value


def _deep_merge(base: dict[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, Mapping)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class ConfigLoader(Generic[TConfig]):
    """Load config data from disk and apply environment overrides."""

    def __init__(
        self,
        config_model: type[TConfig] = ConfigSettings,
        *,
        env_prefix: str = "CONFIG",
        env: Mapping[str, str] | None = None,
        yaml_loader: Callable[[str], Any] | None = None,
        json_loader: Callable[[str], Any] | None = None,
    ) -> None:
        if not isinstance(config_model, type) or not issubclass(config_model, BaseModel):
            raise TypeError("config_model must be a Pydantic BaseModel subclass")
        if not env_prefix:
            raise ValueError("env_prefix must be a non-empty string")

        self._config_model = config_model
        self._env_prefix = env_prefix.upper()
        self._env = env if env is not None else os.environ
        self._yaml_loader = yaml_loader or _load_yaml_text
        self._json_loader = json_loader or json.loads

    def load(self, path: str | Path) -> TConfig:
        source_path = Path(path)
        if not source_path.exists():
            raise FileNotFoundError(source_path)

        raw_text = source_path.read_text(encoding="utf-8")
        parsed_data = self._parse_text(raw_text, source_path.suffix.lower())
        merged = self._apply_env_overrides(parsed_data)
        return self._config_model.model_validate(merged)

    def load_from_mapping(self, data: Mapping[str, Any]) -> TConfig:
        merged = self._apply_env_overrides(dict(data))
        return self._config_model.model_validate(merged)

    def _parse_text(self, text: str, suffix: str) -> dict[str, Any]:
        if suffix in {".yaml", ".yml"}:
            parsed = self._yaml_loader(text)
        elif suffix == ".json":
            parsed = self._json_loader(text)
        else:
            raise ValueError(f"Unsupported configuration file type: {suffix or '<no suffix>'}")

        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ValueError("Configuration file must contain a mapping at the top level")
        return parsed

    def _apply_env_overrides(self, data: Mapping[str, Any]) -> dict[str, Any]:
        overrides: dict[str, Any] = {}

        for env_key, raw_value in self._env.items():
            matched_prefix: str | None = None
            for prefix in (f"{self._env_prefix}__", f"{self._env_prefix}_"):
                if env_key.startswith(prefix):
                    matched_prefix = prefix
                    break

            if matched_prefix is None:
                continue

            path = [
                segment.lower()
                for segment in env_key[len(matched_prefix) :].split("__")
                if segment
            ]
            if not path:
                raise ValueError(f"Invalid environment override key: {env_key}")

            annotation = self._resolve_annotation(path)
            parsed_value = _coerce_value(raw_value, annotation)
            self._set_nested_override(overrides, path, parsed_value)

        return _deep_merge(dict(data), overrides)

    def _resolve_annotation(self, path: list[str]) -> Any:
        current_model: type[BaseModel] = self._config_model
        annotation: Any = None

        for index, part in enumerate(path):
            field_info = current_model.model_fields.get(part)
            if field_info is None:
                joined = "__".join(path[: index + 1])
                raise ValueError(f"Unknown configuration path in environment override: {joined}")

            annotation = field_info.annotation
            annotation = _unwrap_annotation(annotation)

            if index < len(path) - 1:
                if not isinstance(annotation, type) or not issubclass(annotation, BaseModel):
                    joined = "__".join(path[: index + 1])
                    raise ValueError(f"Environment override path is not a nested model: {joined}")
                current_model = annotation

        return annotation

    @staticmethod
    def _set_nested_override(container: dict[str, Any], path: list[str], value: Any) -> None:
        cursor = container
        for part in path[:-1]:
            next_value = cursor.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                cursor[part] = next_value
            cursor = next_value
        cursor[path[-1]] = value


def build_config_loader(
    *,
    config_model: type[TConfig] = ConfigSettings,
    env_prefix: str = "CONFIG",
    env: Mapping[str, str] | None = None,
    yaml_loader: Callable[[str], Any] | None = None,
    json_loader: Callable[[str], Any] | None = None,
) -> ConfigLoader[TConfig]:
    """Public factory that returns a validated, injectable config loader."""

    return ConfigLoader(
        config_model=config_model,
        env_prefix=env_prefix,
        env=env,
        yaml_loader=yaml_loader,
        json_loader=json_loader,
    )


def load_config(
    path: str | Path,
    *,
    config_model: type[TConfig] = ConfigSettings,
    env_prefix: str = "CONFIG",
    env: Mapping[str, str] | None = None,
    yaml_loader: Callable[[str], Any] | None = None,
    json_loader: Callable[[str], Any] | None = None,
) -> TConfig:
    """Convenience entry point for loading and validating a config file."""

    loader = build_config_loader(
        config_model=config_model,
        env_prefix=env_prefix,
        env=env,
        yaml_loader=yaml_loader,
        json_loader=json_loader,
    )
    return loader.load(path)
