"""Email alert provider — sends notifications via SMTP."""

from __future__ import annotations

import logging
from email.mime.text import MIMEText

from tradingbot.monitoring.alerts.base import AlertProvider

logger = logging.getLogger(__name__)


class EmailAlertProvider(AlertProvider):
    """
    Sends alert notifications via email (SMTP).

    Supports TLS connections for secure delivery.
    """

    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        recipient: str = "",
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._recipient = recipient

    async def send(self, title: str, message: str, level: str = "info") -> bool:
        """Send an email notification."""
        try:
            import aiosmtplib

            msg = MIMEText(message)
            msg["Subject"] = f"[TradingBot {level.upper()}] {title}"
            msg["From"] = self._username
            msg["To"] = self._recipient

            await aiosmtplib.send(
                msg,
                hostname=self._smtp_host,
                port=self._smtp_port,
                start_tls=True,
                username=self._username,
                password=self._password,
            )

            logger.debug("Email alert sent: %s", title)
            return True

        except Exception as exc:
            logger.error("Failed to send email alert: %s", exc)
            return False
