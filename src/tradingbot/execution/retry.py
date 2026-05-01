"""Retry logic — exponential backoff with jitter for resilient API calls."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, message: str, attempts: int, last_error: Exception | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


async def retry_async(
    func: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """
    Execute an async function with exponential backoff retry.

    Args:
        func: Async function to call.
        *args: Positional arguments for func.
        max_attempts: Maximum number of attempts (including first try).
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries.
        backoff_factor: Multiplier for delay after each failure.
        jitter: Add random jitter to prevent thundering herd.
        retryable_exceptions: Exception types that trigger retries.
        **kwargs: Keyword arguments for func.

    Returns:
        Return value of the function.

    Raises:
        RetryExhaustedError: If all attempts fail.
    """
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as exc:
            last_error = exc

            if attempt == max_attempts:
                logger.error(
                    "All %d retry attempts exhausted for %s: %s",
                    max_attempts,
                    getattr(func, '__qualname__', str(func)),
                    exc,
                )
                raise RetryExhaustedError(
                    f"Failed after {max_attempts} attempts: {exc}",
                    attempts=max_attempts,
                    last_error=exc,
                ) from exc

            # Calculate delay with exponential backoff
            delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)

            # Add jitter
            if jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(
                "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                attempt,
                max_attempts,
                getattr(func, '__qualname__', str(func)),
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    # Should never reach here, but just in case
    raise RetryExhaustedError(
        f"Failed after {max_attempts} attempts",
        attempts=max_attempts,
        last_error=last_error,
    )
