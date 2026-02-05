from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Awaitable, Callable, ParamSpec, TypeVar

from .broker import Broker
from .errors import RejectError, RetryError
from .logger import get_logger
from .message import Message
from .middleware import DEFAULT, Middleware
from .task import Task

P = ParamSpec("P")
R = TypeVar("R")


class Worker:
    def __init__(
        self,
        name: str,
        broker_url: str = "redis://localhost:6379",
        concurrency: int = 100,
        middlewares: list[Middleware] | None = None,
    ) -> None:
        self.name = name
        self.broker = Broker.from_url(broker_url)
        self.tasks: list[Task] = []
        self.middlewares: list[Middleware] = middlewares or list(DEFAULT)
        self.concurrency: int = concurrency
        self.logger = get_logger(name)

    def register_middleware(self, middleware: Middleware, pos: int = -1) -> None:
        if pos == -1:
            self.middlewares.append(middleware)
        else:
            self.middlewares.insert(pos, middleware)

    def task(
        self,
        **options,
    ) -> Callable[[Callable[P, Awaitable[R]]], Task[P, R]]:
        def decorator(fn: Callable[P, Awaitable[R]]) -> Task[P, R]:
            task_name = f"{self.name}:{fn.__qualname__}"
            task = Task(
                name=task_name,
                fn=fn,
                options=options,
                broker=self.broker,
            )
            self.tasks.append(task)
            return task

        return decorator

    async def _poll(self, task: Task, broker: Broker) -> None:
        sem = asyncio.Semaphore(self.concurrency)
        self.logger.info(f"Polling for Task {task.name}")

        try:
            while True:
                message = await broker.consume(task.name)
                # concurrency limiter, without, queue would be drained in one go.
                await sem.acquire()
                asyncio.create_task(self._process(task, broker, sem, message))
        except asyncio.CancelledError:
            self.logger.info(f"Worker {task.name} cancelled...")
            raise

    async def _process(
        self,
        task: Task,
        broker: Broker,
        sem: asyncio.Semaphore,
        message: Message,
    ) -> None:
        try:
            self.logger.debug(f"Processing message {message.id}")
            try:
                if message.task_name != task.name:
                    # This should never happen.
                    raise RejectError(
                        f"Message {message.id} for unknown task '{message.task_name}' (expected '{task.name}')"
                    )

                async with AsyncExitStack() as stack:
                    for middleware in self.middlewares:
                        await stack.enter_async_context(middleware(message, task))
                    await task.fn(*message.args, **message.kwargs)

                await broker.ack(message)
            except RejectError as e:
                self.logger.warning(f"Message {message.id} rejected: {e}")
                await broker.nack(message, drop=True)
            except RetryError as e:
                self.logger.debug(f"Retrying in {e.delay}s: {e}")
                await broker.nack(message, delay=e.delay or 0)
            except Exception as e:
                self.logger.error(
                    f"Rejected after error in {task.name}: {e}",
                    exc_info=True,
                )
                await broker.nack(message, drop=True)
        finally:
            sem.release()

    async def run(self) -> None:
        try:
            await asyncio.gather(
                *[self._poll(task, self.broker) for task in self.tasks]
            )
        except asyncio.CancelledError:
            self.logger.info("Worker shutting down...")
        finally:
            await self.broker.close()
