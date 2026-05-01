"""Telegram alert provider — sends notifications via Telegram bot."""

from __future__ import annotations

import logging

from tradingbot.monitoring.alerts.base import AlertProvider

logger = logging.getLogger(__name__)

# Alert level emoji mapping
LEVEL_EMOJI = {
    "info": "INFO",
    "warning": "⚠️",
    "critical": "🚨",
}


class TelegramAlertProvider(AlertProvider):
    """
    Sends alert notifications via Telegram.

    Requires a Telegram bot token and chat ID.
    """

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    async def send(self, title: str, message: str, level: str = "info") -> bool:
        """Send a Telegram message."""
        try:
            import aiohttp

            emoji = LEVEL_EMOJI.get(level, "📋")
            text = f"{emoji} *{title}*\n\n{message}"

            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            payload = {
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }

            async with aiohttp.ClientSession() as session, session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.debug("Telegram alert sent: %s", title)
                        return True
                    else:
                        body = await resp.text()
                        logger.error("Telegram API error %d: %s", resp.status, body)
                        return False

        except Exception as exc:
            logger.error("Failed to send Telegram alert: %s", exc)
            return False
