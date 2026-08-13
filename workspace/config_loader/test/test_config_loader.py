from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

CODING = Path(__file__).parents[1] / "Coding"
sys.path.insert(0, str(CODING))

from loader import ConfigLoadError, create_config_loader  # noqa: E402
from schemas import LoaderSettings  # noqa: E402


class DatabaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host: str
    port: int
    enabled: bool = True


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    debug: bool
    database: DatabaseConfig


@pytest.mark.parametrize("suffix", ["json", "yaml", "yml"])
def test_loads_supported_files_into_typed_schema(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"config.{suffix}"
    if suffix == "json":
        path.write_text(
            '{"name":"service","debug":false,"database":{"host":"db","port":5432}}',
            encoding="utf-8",
        )
    else:
        path.write_text(
            "name: service\ndebug: false\ndatabase:\n  host: db\n  port: 5432\n",
            encoding="utf-8",
        )

    result = create_config_loader().load(path, AppConfig, environ={})

    assert result == AppConfig(
        name="service", debug=False, database=DatabaseConfig(host="db", port=5432)
    )


def test_environment_overrides_are_nested_case_insensitive_and_typed(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        '{"name":"file","debug":false,"database":{"host":"old","port":1}}',
        encoding="utf-8",
    )
    loader = create_config_loader({"env_prefix": "SERVICE_"})

    result = loader.load(
        path,
        AppConfig,
        environ={
            "IGNORED_NAME": "wrong",
            "SERVICE_NAME": "environment",
            "SERVICE_DEBUG": "true",
            "SERVICE_DATABASE__HOST": "new-db",
            "SERVICE_DATABASE__PORT": "6543",
            "SERVICE_DATABASE__ENABLED": "false",
        },
    )

    assert result.name == "environment"
    assert result.debug is True
    assert result.database == DatabaseConfig(host="new-db", port=6543, enabled=False)


def test_environment_can_supply_missing_nested_values(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("name: app\ndebug: true\n", encoding="utf-8")

    result = create_config_loader().load(
        path,
        AppConfig,
        environ={"APP_DATABASE__HOST": "db", "APP_DATABASE__PORT": "5432"},
    )

    assert result.database.port == 5432


def test_environment_is_looked_up_at_load_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        '{"name":"file","debug":false,"database":{"host":"db","port":5432}}',
        encoding="utf-8",
    )
    loader = create_config_loader()
    monkeypatch.setenv("APP_NAME", "first")

    assert loader.load(path, AppConfig).name == "first"

    monkeypatch.setenv("APP_NAME", "second")
    assert loader.load(path, AppConfig).name == "second"


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("config.toml", "name='app'", "unsupported configuration format"),
        ("config.json", "{bad", "invalid JSON configuration"),
        ("config.yaml", "key: [", "invalid YAML configuration"),
        ("config.json", "[]", "configuration root must be"),
    ],
)
def test_rejects_unsupported_malformed_or_non_mapping_files(
    tmp_path: Path, filename: str, content: str, message: str
) -> None:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigLoadError, match=message):
        create_config_loader().load(path, AppConfig, environ={})


def test_wraps_missing_file_error_without_leaking_details(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(ConfigLoadError, match="unable to read configuration file") as error:
        create_config_loader().load(path, AppConfig, environ={})

    assert isinstance(error.value.__cause__, FileNotFoundError)


def test_schema_validation_rejects_invalid_configuration(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        '{"name":"service","debug":false,"database":{"host":"db","port":"bad"}}',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        create_config_loader().load(path, AppConfig, environ={})


def test_validates_schema_factory_settings_and_environment_names(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(TypeError, match="Pydantic BaseModel"):
        create_config_loader().load(path, dict, environ={})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="settings must be"):
        create_config_loader("APP_")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        LoaderSettings(env_prefix="")
    with pytest.raises(ValidationError):
        LoaderSettings(env_nested_delimiter="")
    with pytest.raises(ConfigLoadError, match="invalid environment override name"):
        create_config_loader().load(path, AppConfig, environ={"APP_": "bad"})


def test_rejects_override_that_traverses_a_scalar(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        '{"name":"service","debug":false,"database":"not-an-object"}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError, match="conflicts with a scalar"):
        create_config_loader().load(
            path, AppConfig, environ={"APP_DATABASE__HOST": "db"}
        )


def test_empty_yaml_is_validated_as_empty_mapping(tmp_path: Path) -> None:
    class OptionalConfig(BaseModel):
        value: str = "default"

    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    assert create_config_loader().load(path, OptionalConfig, environ={}).value == "default"


@pytest.mark.parametrize(
    "content",
    ["1: value\n", "database:\n  5432: value\n"],
)
def test_rejects_non_string_yaml_mapping_keys(tmp_path: Path, content: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="mapping keys must be strings"):
        create_config_loader().load(path, AppConfig, environ={"APP_NAME": "safe"})


def test_rejects_unknown_encoding_when_settings_are_validated() -> None:
    with pytest.raises(ValidationError, match="registered codec"):
        create_config_loader({"encoding": "definitely-not-a-real-codec"})
