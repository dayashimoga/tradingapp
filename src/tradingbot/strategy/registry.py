"""Strategy registry — discovers and manages trading strategies."""

from __future__ import annotations

import logging
from typing import Any

from tradingbot.core.event_bus import EventBus
from tradingbot.strategy.base import Strategy

logger = logging.getLogger(__name__)

# Global strategy registry
_REGISTRY: dict[str, type[Strategy]] = {}


def register_strategy(name: str) -> Any:
    """
    Decorator to register a strategy class.

    Usage:
        @register_strategy("my_strategy")
        class MyStrategy(Strategy):
            ...
    """

    def decorator(cls: type[Strategy]) -> type[Strategy]:
        if name in _REGISTRY:
            logger.warning("Overwriting existing strategy: %s", name)
        _REGISTRY[name] = cls
        logger.debug("Registered strategy: %s -> %s", name, cls.__name__)
        return cls

    return decorator


def get_strategy(
    name: str,
    params: dict[str, Any] | None = None,
    event_bus: EventBus | None = None,
) -> Strategy:
    """
    Create a strategy instance by name.

    Args:
        name: Registered strategy name.
        params: Strategy-specific parameters.
        event_bus: Event bus for publishing signals.

    Returns:
        Configured Strategy instance.

    Raises:
        KeyError: If strategy name is not registered.
    """
    if name not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise KeyError(f"Unknown strategy '{name}'. Available: {available}")

    strategy_class = _REGISTRY[name]
    strategy = strategy_class(name=name, params=params or {}, event_bus=event_bus)
    logger.info("Created strategy: %s (%s)", name, strategy_class.__name__)
    return strategy


def list_strategies() -> list[str]:
    """List all registered strategy names."""
    return list(_REGISTRY.keys())


def clear_registry() -> None:
    """Clear the strategy registry (useful for testing)."""
    _REGISTRY.clear()
