import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

import sys

CODING_DIR = Path(__file__).resolve().parents[1] / "Coding"
if str(CODING_DIR) not in sys.path:
    sys.path.insert(0, str(CODING_DIR))

from errors import ConfigLoadError, ConfigValidationError
from loader import ConfigLoader, load_config, validate_config
from schemas import AppConfig, DatabaseConfig


class ConfigLoaderTests(unittest.TestCase):
    def _write(self, root: Path, name: str, content: str) -> Path:
        path = root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_yaml_config_and_applies_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._write(
                root,
                "config.yaml",
                """
service_name: api
environment: dev
database:
  url: sqlite:///app.db
""".strip(),
            )

            config = load_config(path)

            self.assertIsInstance(config, AppConfig)
            self.assertEqual(config.service_name, "api")
            self.assertEqual(config.database.url, "sqlite:///app.db")
            self.assertEqual(config.database.pool_size, 5)
            self.assertEqual(config.port, 8000)
            self.assertFalse(config.features.enable_cache)

    def test_loads_json_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._write(
                root,
                "config.json",
                """
{
  "service_name": "worker",
  "environment": "prod",
  "debug": false,
  "port": 9000,
  "database": {
    "url": "postgresql://db/app",
    "pool_size": 10
  },
  "features": {
    "enable_cache": true
  }
}
""".strip(),
            )

            config = load_config(path)

            self.assertEqual(config.environment, "prod")
            self.assertEqual(config.port, 9000)
            self.assertTrue(config.features.enable_cache)

    def test_environment_overrides_take_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._write(
                root,
                "config.yaml",
                """
service_name: api
debug: false
database:
  url: sqlite:///app.db
  pool_size: 5
""".strip(),
            )

            loader = ConfigLoader(
                env={
                    "APP_DEBUG": "true",
                    "APP_DATABASE_POOL_SIZE": "12",
                    "APP_FEATURES_ENABLE_METRICS": "true",
                }
            )
            config = loader.load(path)

            self.assertTrue(config.debug)
            self.assertEqual(config.database.pool_size, 12)
            self.assertTrue(config.features.enable_metrics)

    def test_validation_failure_is_wrapped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._write(
                root,
                "config.yaml",
                """
service_name: api
port: 70000
database:
  url: sqlite:///app.db
""".strip(),
            )

            with self.assertRaises(ConfigValidationError) as ctx:
                load_config(path)

            self.assertIn("port", str(ctx.exception))

    def test_invalid_json_raises_load_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._write(
                root,
                "config.json",
                "{not valid json}",
            )

            with self.assertRaises(ConfigLoadError):
                load_config(path)

    def test_missing_config_file_raises_load_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "missing.yaml"

            with self.assertRaises(ConfigLoadError) as ctx:
                load_config(path)

            self.assertIn(str(path), str(ctx.exception))

    def test_validate_config_rejects_extra_fields(self) -> None:
        with self.assertRaises(ConfigValidationError):
            validate_config(
                AppConfig,
                {
                    "service_name": "api",
                    "database": {"url": "sqlite:///app.db"},
                    "unexpected": True,
                },
            )

    def test_schema_validation_can_be_used_directly(self) -> None:
        config = validate_config(
            DatabaseConfig,
            {"url": "sqlite:///app.db", "pool_size": "3"},
        )

        self.assertEqual(config.pool_size, 3)


if __name__ == "__main__":
    unittest.main()
