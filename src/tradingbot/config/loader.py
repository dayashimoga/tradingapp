"""Configuration loader — loads, merges, and validates configuration from multiple sources."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from tradingbot.config.schema import TradingBotConfig

logger = logging.getLogger(__name__)

# Default config search paths
DEFAULT_CONFIG_PATHS = [
    Path("config/default.yaml"),
    Path("config/local.yaml"),
]

ENV_PREFIX = "TRADINGBOT_"


def load_yaml_file(path: Path) -> dict[str, Any]:
    """
    Load a YAML configuration file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(f"Configuration file must contain a YAML mapping, got {type(data)}")

    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries. Override values take precedence.

    Args:
        base: Base configuration dictionary.
        override: Override configuration dictionary.

    Returns:
        Merged configuration dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_env_overrides() -> dict[str, Any]:
    """
    Load configuration overrides from environment variables.

    Environment variables are expected in the format:
        TRADINGBOT_SECTION_KEY=value

    For example:
        TRADINGBOT_BOT_MODE=live
        TRADINGBOT_RISK_MAX_DAILY_LOSS=1000

    Returns:
        Dictionary of environment-based overrides.
    """
    overrides: dict[str, Any] = {}

    for key, value in os.environ.items():
        if not key.startswith(ENV_PREFIX):
            continue

        # Remove prefix and split into parts
        parts = key[len(ENV_PREFIX) :].lower().split("_", 1)
        if len(parts) < 2:
            continue

        section, param = parts[0], parts[1]

        if section not in overrides:
            overrides[section] = {}

        # Try to parse as number/bool
        overrides[section][param] = _parse_env_value(value)

    return overrides


def _parse_env_value(value: str) -> str | int | float | bool:
    """Parse an environment variable value to its appropriate Python type."""
    # Boolean
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    # Float
    try:
        return float(value)
    except ValueError:
        pass

    return value


def load_config(
    config_path: Path | str | None = None,
    extra_overrides: dict[str, Any] | None = None,
) -> TradingBotConfig:
    """
    Load and validate trading bot configuration.

    Merge hierarchy (later sources override earlier):
    1. Built-in defaults (from Pydantic schema)
    2. Default config file (config/default.yaml)
    3. User-specified config file
    4. Environment variables (TRADINGBOT_* prefix)
    5. Programmatic overrides

    Args:
        config_path: Optional path to a custom config file.
        extra_overrides: Optional dictionary of programmatic overrides.

    Returns:
        Validated TradingBotConfig instance.
    """
    merged: dict[str, Any] = {}

    # 1. Load default config file if it exists
    default_path = Path("config/default.yaml")
    if default_path.exists():
        try:
            default_data = load_yaml_file(default_path)
            merged = deep_merge(merged, default_data)
            logger.debug("Loaded default config from %s", default_path)
        except Exception as exc:
            logger.warning("Failed to load default config: %s", exc)

    # 2. Load user-specified config file
    if config_path is not None:
        path = Path(config_path)
        user_data = load_yaml_file(path)
        merged = deep_merge(merged, user_data)
        logger.info("Loaded config from %s", path)

    # 3. Apply environment variable overrides
    env_overrides = load_env_overrides()
    if env_overrides:
        merged = deep_merge(merged, env_overrides)
        logger.debug("Applied %d environment overrides", len(env_overrides))

    # 4. Apply programmatic overrides
    if extra_overrides:
        merged = deep_merge(merged, extra_overrides)
        logger.debug("Applied programmatic overrides")

    # 5. Validate with Pydantic
    config = TradingBotConfig(**merged)
    logger.info(
        "Configuration loaded: mode=%s, strategy=%s, symbols=%s",
        config.bot.mode,
        config.strategy.name,
        config.data.symbols,
    )

    return config
