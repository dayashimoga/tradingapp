"""Abstract base class for alert providers."""

from __future__ import annotations

import abc


class AlertProvider(abc.ABC):
    """Abstract alert provider interface."""

    @abc.abstractmethod
    async def send(self, title: str, message: str, level: str = "info") -> bool:
        """
        Send an alert notification.

        Args:
            title: Alert title.
            message: Alert body.
            level: Severity level.

        Returns:
            True if sent successfully.
        """
