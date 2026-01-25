from __future__ import annotations

from functools import update_wrapper
from typing import Awaitable, Callable, Generic, ParamSpec, TypeVar

from .message import Message
from .q import Queue

P = ParamSpec("P")
R = TypeVar("R")


class Task(Generic[P, R]):
    def __init__(
        self,
        name: str,
        fn: Callable[P, Awaitable[R]],
        queue: Queue,
        ttl: int | None = None,
    ) -> None:
        self.name = name
        self.fn = fn
        self.queue = queue
        self.ttl = ttl

    def message(self, *args: P.args, **kwargs: P.kwargs) -> Message:
        return Message(
            args=args,
            kwargs=kwargs,
            task=self.name,
        )

    async def send(self, *args: P.args, **kwargs: P.kwargs) -> str:
        message = self.message(*args, **kwargs)
        await self.queue.put([message], ttl=self.ttl)
        return message.id

    async def send_bulk(self, messages: list[Message]) -> list[str]:
        await self.queue.put(messages, ttl=self.ttl)
        return [message.id for message in messages]

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return await self.fn(*args, **kwargs)
