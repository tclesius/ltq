from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

from .errors import RetryMessage
from .message import Message
from .logger import get_logger

logger = get_logger()
Handler = Callable[[Message], Awaitable[Any]]


class Middleware(ABC):
    @abstractmethod
    async def handle(self, message: Message, next_handler: Handler) -> Any: ...


class Retry(Middleware):
    def __init__(
        self,
        max_retries: int = 3,
        min_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff: float = 2.0,
    ):
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.backoff = backoff

    async def handle(self, message: Message, next_handler: Handler) -> Any:
        retries = message.ctx.get("retries", 0)

        try:
            return await next_handler(message)
        except Exception as e:
            retries += 1
            message.ctx["retries"] = retries
            max_retries = max(self.max_retries - 1, 0)

            if retries > max_retries:
                raise

            delay = min(
                self.min_delay * (self.backoff ** (retries - 1)),
                self.max_delay,
            )
            logger.warning(
                f"Retry attempt {retries}/{max_retries} ({type(e).__name__})",
                exc_info=True,
            )
            raise RetryMessage(delay, str(e))


class RateLimit(Middleware):
    def __init__(self, requests_per_second: float):
        self.min_interval = 1.0 / requests_per_second
        self._last_request: float = 0
        self._lock = asyncio.Lock()

    async def handle(self, message: Message, next_handler: Handler) -> Any:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_request = time.monotonic()

        return await next_handler(message)


class Timeout(Middleware):
    def __init__(self, timeout: float):
        self.timeout = timeout

    async def handle(self, message: Message, next_handler: Handler) -> Any:
        return await asyncio.wait_for(next_handler(message), timeout=self.timeout)


class Sentry(Middleware):
    def __init__(self, dsn: str, **kwargs: Any) -> None:
        try:
            import sentry_sdk  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Sentry middleware requires optional dependency 'sentry-sdk'. "
                "Install with 'ltq[sentry]'."
            ) from exc

        self.sentry = sentry_sdk
        self.sentry.init(dsn=dsn, send_default_pii=True, **kwargs)

    async def handle(self, message: Message, next_handler: Handler) -> Any:
        with self.sentry.push_scope() as scope:
            scope.set_tag("task", message.task_name)
            scope.set_tag("message_id", message.id)
            scope.set_context(
                "message",
                {
                    "id": message.id,
                    "task": message.task_name,
                    "args": message.args,
                    "kwargs": message.kwargs,
                    "ctx": message.ctx,
                },
            )

            try:
                return await next_handler(message)
            except RetryMessage:
                raise
            except Exception as e:
                self.sentry.capture_exception(e)
                raise
