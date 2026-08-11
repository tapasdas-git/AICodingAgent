from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import TestCase

from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.config_loader.Coding.loader import (  # noqa: E402
    ConfigLoader,
    build_config_loader,
    load_config,
)
from workspace.config_loader.Coding.schemas import ConfigSettings, DatabaseConfig  # noqa: E402


def _write_file(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


class ConfigLoaderTests(TestCase):
    def _base_config(self) -> dict[str, Any]:
        return {
            "app_name": "example-app",
            "debug": False,
            "host": "127.0.0.1",
            "port": 8000,
            "retries": 2,
            "timeout_seconds": 15.0,
            "tags": ["alpha", "beta"],
            "allowed_hosts": ["localhost"],
            "database": {"url": "sqlite:///tmp.db", "pool_size": 4, "echo": False},
            "logging": {"level": "INFO", "format": "%(message)s"},
        }

    def test_yaml_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = _write_file(
                temp_path,
                "config.yaml",
                "\n".join(
                    [
                        "app_name: yaml-app",
                        "debug: true",
                        "host: 0.0.0.0",
                        "port: 9000",
                        "retries: 5",
                        "timeout_seconds: 22.5",
                        "tags:",
                        "  - one",
                        "  - two",
                        "allowed_hosts:",
                        "  - example.com",
                        "database:",
                        "  url: postgresql://localhost/app",
                        "  pool_size: 12",
                        "  echo: false",
                        "logging:",
                        "  level: WARNING",
                        "  format: '%(levelname)s:%(message)s'",
                    ]
                ),
            )

            config = load_config(config_path, env={})

            self.assertEqual(config.app_name, "yaml-app")
            self.assertTrue(config.debug)
            self.assertEqual(config.port, 9000)
            self.assertEqual(config.tags, ["one", "two"])
            self.assertIsInstance(config.database, DatabaseConfig)
            self.assertEqual(config.database.url, "postgresql://localhost/app")
            self.assertEqual(config.logging.level, "WARNING")

    def test_json_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = _write_file(
                temp_path,
                "config.json",
                json.dumps(self._base_config()),
            )

            loader = build_config_loader(env={})
            config = loader.load(config_path)

            self.assertEqual(config.app_name, "example-app")
            self.assertEqual(config.database.pool_size, 4)
            self.assertEqual(config.allowed_hosts, ["localhost"])

    def test_environment_variable_overrides_nested_and_scalar_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = _write_file(
                temp_path,
                "config.json",
                json.dumps(self._base_config()),
            )

            env = {
                "CONFIG_DEBUG": "true",
                "CONFIG_PORT": "8081",
                "CONFIG_DATABASE__POOL_SIZE": "20",
                "CONFIG_ALLOWED_HOSTS": "api.example.com,admin.example.com",
                "CONFIG_LOGGING__LEVEL": "ERROR",
            }

            config = load_config(config_path, env=env)

            self.assertTrue(config.debug)
            self.assertEqual(config.port, 8081)
            self.assertEqual(config.database.pool_size, 20)
            self.assertEqual(config.allowed_hosts, ["api.example.com", "admin.example.com"])
            self.assertEqual(config.logging.level, "ERROR")

    def test_validation_failure_for_invalid_config_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = _write_file(
                temp_path,
                "config.yaml",
                "\n".join(
                    [
                        "app_name: broken-app",
                        "port: 70000",
                        "database:",
                        "  url: sqlite:///tmp.db",
                    ]
                ),
            )

            with self.assertRaises(ValidationError):
                load_config(config_path, env={})

    def test_unsupported_file_extension_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = _write_file(temp_path, "config.txt", "app_name=plain-text")

            with self.assertRaises(ValueError):
                load_config(config_path, env={})

    def test_unknown_environment_path_raises_value_error(self) -> None:
        loader = ConfigLoader(ConfigSettings, env={"CONFIG_DOES_NOT_EXIST": "value"})

        with self.assertRaises(ValueError):
            loader.load_from_mapping(self._base_config())
