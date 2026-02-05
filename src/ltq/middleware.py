from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
import random
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from .errors import RejectError, RetryError

if TYPE_CHECKING:
    from .message import Message
    from .task import Task


class Middleware(ABC):
    @abstractmethod
    @asynccontextmanager
    async def __call__(self, message: Message, task: Task) -> AsyncIterator[None]:
        yield


class MaxTries(Middleware):
    @asynccontextmanager
    async def __call__(self, message: Message, task: Task) -> AsyncIterator[None]:
        max_tries = task.options.get("max_tries")
        if max_tries is not None:
            if message.ctx.get("tries", 0) >= max_tries:
                raise RejectError(f"Message {message.id} exceeded max tries")

        try:
            yield
        except Exception:
            if not message.ctx.pop("rate_limited", False):
                message.ctx["tries"] = message.ctx.get("tries", 0) + 1
            raise


class MaxAge(Middleware):
    @asynccontextmanager
    async def __call__(self, message: Message, task: Task) -> AsyncIterator[None]:
        max_age: timedelta | None = task.options.get("max_age")
        created_at = message.ctx.get("created_at")

        if max_age is not None and created_at is not None:
            age = time.time() - float(created_at)
            if age > max_age.total_seconds():
                raise RejectError(f"Message {message.id} too old")

        yield


class MaxRate(Middleware):
    def __init__(self) -> None:
        self.last_times: dict[str, float] = {}

    @lru_cache(maxsize=128)
    def _parse_rate(self, rate: str) -> float:
        count, unit = rate.split("/")
        count = float(count)
        unit = unit.strip().lower()

        if unit == "s":
            return count
        elif unit == "m":
            return count / 60
        elif unit == "h":
            return count / 3600
        else:
            raise ValueError(f"Invalid rate unit: {unit}. Use 's', 'm', or 'h'")

    @asynccontextmanager
    async def __call__(self, message: Message, task: Task) -> AsyncIterator[None]:
        max_rate = task.options.get("max_rate")
        if max_rate:
            now = time.time()
            last = self.last_times.get(message.task_name, 0.0)
            elapsed = now - last
            rate_per_sec = self._parse_rate(max_rate)
            interval = 1.0 / rate_per_sec

            if elapsed < interval:
                base_delay = interval - elapsed
                delay = base_delay * 0.5 + random.uniform(0, base_delay * 0.5)
                message.ctx["rate_limited"] = True
                raise RetryError(delay=delay)

            self.last_times[message.task_name] = now
        yield


class Sentry(Middleware):
    def __init__(self, dsn: str) -> None:
        self.sentry = None
        try:
            import sentry_sdk  # type: ignore

            sentry_sdk.init(dsn=dsn)
            self.sentry = sentry_sdk
        except ImportError:
            pass

    @asynccontextmanager
    async def __call__(self, message: Message, task: Task) -> AsyncIterator[None]:
        try:
            yield
        except Exception as e:
            if self.sentry:
                self.sentry.capture_exception(e)
            raise


DEFAULT: list[Middleware] = [MaxTries(), MaxAge(), MaxRate()]
