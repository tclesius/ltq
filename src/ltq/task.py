from __future__ import annotations

from typing import Awaitable, Callable, Generic, ParamSpec, TypeVar

from .broker import Broker
from .message import Message

P = ParamSpec("P")
R = TypeVar("R")


class Task(Generic[P, R]):
    def __init__(
        self,
        broker: Broker,
        name: str,
        fn: Callable[P, Awaitable[R]],
        options: dict | None = None,
    ) -> None:
        self.name = name
        self.fn = fn
        self.options = options or {}
        self.broker = broker

    def message(self, *args: P.args, **kwargs: P.kwargs) -> Message:
        return Message(
            args=args,
            kwargs=kwargs,
            task_name=self.name,
        )

    async def send(self, *args: P.args, **kwargs: P.kwargs) -> None:
        await self.broker.publish(self.message(*args, **kwargs))

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return await self.fn(*args, **kwargs)
