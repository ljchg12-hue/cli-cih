"""Configuration storage and management for CLI-CIH."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from cli_cih.models.config import Config

# Default config directory
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "cli-cih"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"


class ConfigStorage:
    """Configuration storage manager."""

    def __init__(self, config_path: Path | None = None):
        """Initialize config storage.

        Args:
            config_path: Custom config file path.
        """
        self.config_path = config_path or DEFAULT_CONFIG_FILE
        self._config: Config | None = None

    def ensure_config_dir(self) -> None:
        """Ensure config directory exists."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Config:
        """Load configuration from file.

        Returns:
            Config object.
        """
        if self._config is not None:
            return self._config

        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = yaml.safe_load(f) or {}
                self._config = Config(**data)
            except (yaml.YAMLError, ValidationError):
                # Return default config on error
                self._config = Config()
        else:
            self._config = Config()

        return self._config

    def save(self, config: Config | None = None) -> None:
        """Save configuration to file.

        Args:
            config: Config to save. Uses current config if not provided.
        """
        self.ensure_config_dir()

        if config is not None:
            self._config = config

        if self._config is None:
            self._config = Config()

        with open(self.config_path, "w") as f:
            yaml.dump(
                self._config.model_dump(),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    def reset(self) -> Config:
        """Reset to default configuration.

        Returns:
            Default Config object.
        """
        self._config = Config()
        self.save()
        return self._config


# Global config storage instance
_storage: ConfigStorage | None = None


def get_storage() -> ConfigStorage:
    """Get global config storage instance."""
    global _storage
    if _storage is None:
        _storage = ConfigStorage()
    return _storage


def get_config() -> Config:
    """Get current configuration.

    Returns:
        Config object.
    """
    return get_storage().load()


def save_config(config: Config) -> None:
    """Save configuration.

    Args:
        config: Config to save.
    """
    get_storage().save(config)
