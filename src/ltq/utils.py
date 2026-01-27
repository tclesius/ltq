from __future__ import annotations

from collections import defaultdict

from .message import Message
from .q import Queue


async def dispatch(messages: list[Message]) -> list[str]:
    by_queue: defaultdict[Queue, list[Message]] = defaultdict(list)
    for msg in messages:
        if msg.task is None:
            raise ValueError(f"Message {msg.id} has no task assigned")
        by_queue[msg.task.queue].append(msg)

    for queue, batch in by_queue.items():
        await queue.put(batch)

    return [msg.id for msg in messages]
