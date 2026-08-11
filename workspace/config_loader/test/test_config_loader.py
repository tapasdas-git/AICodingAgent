import tempfile
import unittest
from pathlib import Path

from config_loader import (
    AppConfig,
    ConfigFileError,
    ConfigLoader,
    ConfigValidationError,
    EnvironmentOverrideError,
    load_config,
)


class ConfigLoaderTests(unittest.TestCase):
    def _write(self, root: Path, name: str, content: str) -> Path:
        path = root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_yaml_and_applies_nested_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._write(
                root,
                "settings.yaml",
                """
name: example
environment: development
debug: false
retries: 2
allowed_hosts:
  - example.test
database:
  host: db.local
  port: 5432
  username: app
  password: secret
  database: app_db
""".strip(),
            )

            loader = ConfigLoader(
                AppConfig,
                env={
                    "APP_DEBUG": "true",
                    "APP_DATABASE__PORT": "6543",
                    "APP_ALLOWED_HOSTS": '["example.test", "localhost"]',
                },
            )

            result = loader.load(config)

            self.assertTrue(result.debug)
            self.assertEqual(result.database.port, 6543)
            self.assertEqual(result.allowed_hosts, ["example.test", "localhost"])

    def test_loads_json_via_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._write(
                root,
                "settings.json",
                """
{
  "name": "json-app",
  "environment": "production",
  "database": {
    "host": "db.example",
    "port": 5432,
    "username": "json",
    "password": "secret",
    "database": "json_db"
  }
}
""".strip(),
            )

            result = load_config(config, AppConfig, env={})

            self.assertEqual(result.name, "json-app")
            self.assertEqual(result.environment, "production")
            self.assertEqual(result.database.host, "db.example")

    def test_rejects_unknown_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._write(
                root,
                "settings.yaml",
                """
name: example
environment: development
database:
  host: db.local
  port: 5432
  username: app
  password: secret
  database: app_db
""".strip(),
            )

            loader = ConfigLoader(AppConfig, env={"APP_NOT_A_FIELD": "1"})

            with self.assertRaisesRegex(EnvironmentOverrideError, "unknown configuration override"):
                loader.load(config)

    def test_rejects_conflicting_scalar_then_branch_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._write(
                root,
                "settings.yaml",
                """
name: example
environment: development
database:
  host: db.local
  port: 5432
  username: app
  password: secret
  database: app_db
""".strip(),
            )

            loader = ConfigLoader(
                AppConfig,
                env={
                    "APP_DATABASE": "primary-db",
                    "APP_DATABASE__HOST": "db.example",
                },
            )

            with self.assertRaisesRegex(
                EnvironmentOverrideError, "conflicting environment overrides"
            ):
                loader.load(config)

    def test_rejects_conflicting_branch_then_scalar_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._write(
                root,
                "settings.yaml",
                """
name: example
environment: development
database:
  host: db.local
  port: 5432
  username: app
  password: secret
  database: app_db
""".strip(),
            )

            loader = ConfigLoader(
                AppConfig,
                env={
                    "APP_DATABASE__HOST": "db.example",
                    "APP_DATABASE": "primary-db",
                },
            )

            with self.assertRaisesRegex(
                EnvironmentOverrideError, "conflicting environment overrides"
            ):
                loader.load(config)

    def test_uses_custom_reader_for_virtual_paths(self) -> None:
        loader = ConfigLoader(
            AppConfig,
            env={},
            file_reader=lambda path: """
name: virtual
environment: production
database:
  host: db.local
  port: 5432
  username: app
  password: secret
  database: app_db
""".strip(),
        )

        result = loader.load(Path("virtual/settings.yaml"))

        self.assertEqual(result.name, "virtual")
        self.assertEqual(result.environment, "production")
        self.assertEqual(result.database.host, "db.local")

    def test_rejects_invalid_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._write(root, "settings.yaml", "name: [broken")

            loader = ConfigLoader(AppConfig, env={})

            with self.assertRaises(ConfigFileError):
                loader.load(config)

    def test_rejects_non_mapping_top_level_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._write(root, "settings.json", '["not", "a", "mapping"]')

            loader = ConfigLoader(AppConfig, env={})

            with self.assertRaisesRegex(ConfigFileError, "top-level configuration data must be a mapping"):
                loader.load(config)

    def test_surfaces_schema_validation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._write(
                root,
                "settings.yaml",
                """
name: example
environment: development
database:
  host: db.local
  port: not-an-int
  username: app
  password: secret
  database: app_db
""".strip(),
            )

            loader = ConfigLoader(AppConfig, env={})

            with self.assertRaises(ConfigValidationError):
                loader.load(config)


if __name__ == "__main__":
    unittest.main()
