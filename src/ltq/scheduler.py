from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .broker import Broker
from .message import Message
from .logger import get_logger

try:
    from croniter import croniter  # type: ignore
except ImportError:
    croniter = None


@dataclass
class ScheduledJob:
    msg: Message
    expr: str
    _cron: Any = field(init=False, repr=False)  # croniter instance
    next_run: datetime = field(init=False)

    def __post_init__(self):
        self._cron = croniter(self.expr, datetime.now())  # type: ignore[misc]
        self.advance()

    def advance(self) -> None:
        self.next_run = self._cron.get_next(datetime)


class Scheduler:
    def __init__(
        self,
        broker_url: str = "redis://localhost:6379",
        poll_interval: float = 10.0,
    ) -> None:
        self.broker = Broker.from_url(broker_url)
        self.poll_interval = poll_interval
        self.jobs: list[ScheduledJob] = []
        self.logger = get_logger("scheduler")
        self.task: asyncio.Task[None] | None = None

    def cron(self, expr: str, msg: Message) -> None:
        if croniter is None:
            raise ModuleNotFoundError(
                "Scheduler requires optional dependency 'croniter'. "
                "Install with 'ltq[scheduler]'."
            )
        self.jobs.append(ScheduledJob(msg, expr))

    async def run(self) -> None:
        self.logger.info("Starting scheduler")
        for job in self.jobs:
            self.logger.info(
                f"{job.msg.task_name} [{job.expr}] next={job.next_run:%H:%M:%S}"
            )

        try:
            while True:
                now = datetime.now()
                due = [job for job in self.jobs if now >= job.next_run]

                if due:
                    try:
                        for job in due:
                            await self.broker.publish(job.msg)
                            self.logger.info(
                                f"Enqueued {job.msg.task_name} scheduled={job.next_run:%H:%M:%S}"
                            )
                            job.advance()
                    except Exception:
                        self.logger.exception("Failed to send scheduled jobs")
                        # Don't advance jobs on failure - they'll retry next poll

                await asyncio.sleep(self.poll_interval)
        finally:
            await self.broker.close()

    def start(self) -> None:
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            self.logger.info("Scheduler stopped")

    def start_background(self) -> None:
        if self.task is not None:
            raise RuntimeError("Scheduler is already running")
        self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self.task is None:
            return
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.task = None
        self.logger.info("Scheduler stopped")
