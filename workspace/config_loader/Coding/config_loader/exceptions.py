"""Configuration loader exceptions."""


class ConfigLoaderError(RuntimeError):
    """Base error for configuration loading failures."""


class ConfigFileError(ConfigLoaderError):
    """Raised when the configuration file cannot be read or parsed."""


class EnvironmentOverrideError(ConfigLoaderError):
    """Raised when an environment override does not match the schema."""


class ConfigValidationError(ConfigLoaderError):
    """Raised when schema validation fails."""

