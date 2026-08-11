from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

CODING_DIR = Path(__file__).resolve().parents[1] / "Coding"
if str(CODING_DIR) not in sys.path:
    sys.path.insert(0, str(CODING_DIR))

from config_loader import (  # noqa: E402
    AppConfig,
    ConfigEnvironmentError,
    ConfigParseError,
    ConfigValidationError,
    apply_environment_overrides,
    load_config,
    load_config_data,
    load_config_file,
)


class ConfigLoaderTests(unittest.TestCase):
    def _write(self, suffix: str, content: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / f"config{suffix}"
        path.write_text(content, encoding="utf-8")
        return path

    def _sample_mapping(self) -> dict[str, object]:
        return {
            "app_name": "inventory-service",
            "environment": "development",
            "debug": False,
            "allowed_hosts": ["localhost", "127.0.0.1"],
            "database": {
                "host": "db.internal",
                "port": 5432,
                "username": "app",
                "password": "secret",
                "database_name": "inventory",
                "pool_size": 10,
                "connect_timeout_seconds": 12.5,
            },
            "logging": {
                "level": "info",
                "format": "%(levelname)s %(message)s",
                "file_path": "/tmp/inventory.log",
            },
        }

    def test_load_yaml_config(self) -> None:
        path = self._write(
            ".yaml",
            "\n".join(
                [
                    "app_name: inventory-service",
                    "environment: development",
                    "debug: false",
                    "allowed_hosts:",
                    "  - localhost",
                    "  - 127.0.0.1",
                    "database:",
                    "  host: db.internal",
                    "  port: 5432",
                    "  username: app",
                    "  password: secret",
                    "  database_name: inventory",
                    "  pool_size: 10",
                    "  connect_timeout_seconds: 12.5",
                    "logging:",
                    "  level: info",
                    "  format: '%(levelname)s %(message)s'",
                    "  file_path: /tmp/inventory.log",
                ]
            ),
        )

        config = load_config(path)

        self.assertIsInstance(config, AppConfig)
        self.assertEqual(config.app_name, "inventory-service")
        self.assertEqual(config.database.host, "db.internal")
        self.assertEqual(config.logging.level, "INFO")
        self.assertEqual(config.allowed_hosts, ["localhost", "127.0.0.1"])

    def test_load_json_config(self) -> None:
        path = self._write(".json", json.dumps(self._sample_mapping()))

        config = load_config_file(path)

        self.assertEqual(config.database.port, 5432)
        self.assertEqual(config.database.database_name, "inventory")
        self.assertEqual(config.logging.file_path, "/tmp/inventory.log")

    def test_environment_overrides_nested_values(self) -> None:
        env = {
            "APP_CONFIG_DEBUG": "true",
            "APP_CONFIG_DATABASE__HOST": "db.override",
            "APP_CONFIG_DATABASE__PORT": "6543",
            "APP_CONFIG_ALLOWED_HOSTS": '["example.com", "api.example.com"]',
        }

        config = load_config_data(self._sample_mapping(), env=env)

        self.assertTrue(config.debug)
        self.assertEqual(config.database.host, "db.override")
        self.assertEqual(config.database.port, 6543)
        self.assertEqual(
            config.allowed_hosts,
            ["example.com", "api.example.com"],
        )

    def test_validation_error_for_missing_required_field(self) -> None:
        payload = self._sample_mapping()
        del payload["database"]

        with self.assertRaises(ConfigValidationError):
            load_config_data(payload)

    def test_validation_error_for_invalid_environment_value(self) -> None:
        env = {"APP_CONFIG_DATABASE__PORT": "not-a-number"}

        with self.assertRaises(ConfigValidationError):
            load_config_data(self._sample_mapping(), env=env)

    def test_environment_error_for_unknown_override_path(self) -> None:
        env = {"APP_CONFIG_DATABASE__UNKNOWN": "value"}

        with self.assertRaises(ConfigEnvironmentError):
            load_config_data(self._sample_mapping(), env=env)

    def test_environment_error_for_malformed_override_key_with_empty_segments(self) -> None:
        malformed_env = {
            "APP_CONFIG_DATABASE____HOST": "db.override",
            "APP_CONFIG_DATABASE__HOST__": "db.override",
        }

        for key, value in malformed_env.items():
            with self.subTest(key=key):
                with self.assertRaises(ConfigEnvironmentError):
                    load_config_data(self._sample_mapping(), env={key: value})

    def test_parse_error_for_invalid_yaml(self) -> None:
        path = self._write(".yaml", "app_name: demo\nlogging:\n  level: [unterminated")

        with self.assertRaises(ConfigParseError):
            load_config(path)

    def test_apply_environment_overrides_does_not_mutate_input(self) -> None:
        payload = self._sample_mapping()
        original = json.loads(json.dumps(payload))

        merged = apply_environment_overrides(
            payload,
            env={"APP_CONFIG_DATABASE__POOL_SIZE": "20"},
        )

        self.assertEqual(payload, original)
        self.assertEqual(merged["database"]["pool_size"], 20)


if __name__ == "__main__":
    unittest.main()
