"""Configuration loader exceptions."""


class ConfigError(Exception):
    """Base class for configuration errors."""


class ConfigLoadError(ConfigError):
    """Raised when a configuration file cannot be parsed or read."""


class ConfigValidationError(ConfigError):
    """Raised when parsed configuration data fails schema validation."""

