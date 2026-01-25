from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, ParamSpec, TypeVar

import redis.asyncio as redis

from .errors import RetryMessage
from .task import Task
from .message import Message
from .middleware import Handler, Middleware
from .q import Queue
from .logger import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

logger = get_logger()


P = ParamSpec("P")
R = TypeVar("R")


class Worker:
    def __init__(
        self,
        url: str = "redis://localhost:6379",
        middlewares: list[Middleware] | None = None,
        concurrency: int = 250,
        poll_sleep: float = 0.1,
    ) -> None:
        self.client: AsyncRedis = redis.from_url(url)
        self.tasks: list[Task] = []
        self.middlewares: list[Middleware] = middlewares or []
        self.concurrency: int = concurrency
        self.poll_sleep: float = poll_sleep

    def task(
        self,
        queue_name: str | None = None,
        ttl: int | None = None,
    ) -> Callable[[Callable[P, Awaitable[R]]], Task[P, R]]:
        def decorator(fn: Callable[P, Awaitable[R]]) -> Task[P, R]:
            filename = Path(fn.__code__.co_filename).stem
            task_name = f"{filename}:{fn.__qualname__}"
            queue = Queue(self.client, queue_name or task_name)
            task = Task(
                name=task_name,
                fn=fn,
                queue=queue,
                ttl=ttl,
            )
            self.tasks.append(task)
            return task

        return decorator

    async def worker(self, task: Task):
        async def base(message: Message) -> Any:
            return await task.fn(*message.args, **message.kwargs)

        handler: Handler = base
        for middleware in reversed(self.middlewares):
            handler = partial(middleware.handle, next_handler=handler)

        while True:
            messages = await task.queue.get(self.concurrency)
            if not messages:
                await asyncio.sleep(self.poll_sleep)
                continue

            logger.debug(f"Processing {len(messages)} messages for {task.name}")

            async def process(msg: Message) -> None:
                try:
                    await handler(msg)
                except RetryMessage as e:
                    logger.warning(f"Retrying in {e.delay}s: {e}")
                    await task.queue.put([msg], delay=e.delay)
                except Exception as e:
                    logger.error(
                        f"Rejected after error in {task.name}: {e}",
                        exc_info=True,
                    )

            await asyncio.gather(*(process(m) for m in messages))
            await task.queue.ack(messages)

    async def run(self) -> None:
        try:
            workers = (self.worker(task) for task in self.tasks)
            await asyncio.gather(*workers)
        finally:
            await self.client.aclose()
