"""Exception hierarchy for configuration loading."""


class ConfigError(Exception):
    """Base class for configuration-related errors."""


class ConfigParseError(ConfigError):
    """Raised when a configuration file cannot be parsed."""


class ConfigValidationError(ConfigError):
    """Raised when parsed configuration data fails schema validation."""


class ConfigEnvironmentError(ConfigError):
    """Raised when environment overrides are malformed or unsupported."""
