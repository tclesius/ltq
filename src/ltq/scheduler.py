from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .message import Message
from .utils import dispatch
from .logger import get_logger

try:
    from croniter import croniter
except ImportError:
    croniter = None

if TYPE_CHECKING:
    from .task import Task


@dataclass
class ScheduledJob:
    task: Task
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
    def __init__(self, poll_interval: float = 10.0) -> None:
        self.poll_interval = poll_interval
        self.jobs: list[ScheduledJob] = []
        self.logger = get_logger("ltq.scheduler")
        self._running = False

    def cron(self, expr: str, msg: Message) -> None:
        if croniter is None:
            raise ModuleNotFoundError(
                "Scheduler requires optional dependency 'croniter'. "
                "Install with 'ltq[scheduler]'."
            )
        if msg.task is None:
            raise ValueError("Message must have a task assigned to use with scheduler")
        self.jobs.append(ScheduledJob(msg.task, msg, expr))

    def run(self) -> None:
        self._running = True
        self.logger.info("Starting scheduler")
        for job in self.jobs:
            self.logger.info(
                f"{job.task.name} [{job.expr}] next={job.next_run:%H:%M:%S}"
            )

        loop = asyncio.new_event_loop()
        while self._running:
            now = datetime.now()
            due = [job for job in self.jobs if now >= job.next_run]
            if due:
                try:
                    loop.run_until_complete(dispatch([job.msg for job in due]))
                    for job in due:
                        self.logger.info(
                            f"Enqueued {job.task.name} scheduled={job.next_run:%H:%M:%S}"
                        )
                except Exception:
                    self.logger.exception("Failed to dispatch scheduled jobs")
                for job in due:
                    job.advance()
            time.sleep(self.poll_interval)
        loop.close()

    def stop(self) -> None:
        self._running = False
