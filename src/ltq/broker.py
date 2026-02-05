from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse
import uuid
from collections import defaultdict

import redis.asyncio as aioredis

from .message import Message


class Broker:
    @staticmethod
    def from_url(url: str) -> Broker:
        urlp = urlparse(url)
        if urlp.scheme == "memory":
            return MemoryBroker()
        elif urlp.scheme == "redis":
            return RedisBroker(url)
        else:
            raise RuntimeError(f"Unknown scheme: {urlp.scheme}")

    async def close(self) -> None: ...
    async def publish(self, message: Message, delay: float = 0) -> None: ...
    async def consume(self, queue: str) -> Message: ...
    async def ack(self, message: Message) -> None: ...
    async def nack(
        self,
        message: Message,
        delay: float = 0,
        drop: bool = False,
    ) -> None: ...
    async def len(self, queue: str) -> int: ...
    async def clear(self, queue: str) -> None: ...


class RedisBroker(Broker):
    def __init__(self, url: str) -> None:
        self.url = url
        self._client = aioredis.from_url(url)
        self._id = uuid.uuid4().hex[:8]

    async def close(self) -> None:
        await self._client.aclose()

    async def publish(
        self,
        message: Message,
        delay: float = 0,
    ) -> None:
        score = time.time() + delay
        await self._client.zadd(
            f"queue:{message.task_name}",
            {
                message.to_json(): score,
            },
        )  # type: ignore

    async def consume(self, queue: str) -> Message:
        while True:
            now = time.time()
            ready = await self._client.zrangebyscore(
                f"queue:{queue}", 0, now, start=0, num=1
            )  # type: ignore
            if ready:
                msg = ready[0]
                await self._client.zadd(f"processing:{queue}:{self._id}", {msg: now,})  # type: ignore
                await self._client.zrem(f"queue:{queue}", msg)  # type: ignore
                return Message.from_json(msg)
            await asyncio.sleep(0.1)

    async def ack(self, message: Message) -> None:
        key = f"processing:{message.task_name}:{self._id}"
        await self._client.zrem(key, message.to_json())  # type: ignore

    async def nack(
        self,
        message: Message,
        delay: float = 0,
        drop: bool = False,
    ) -> None:
        key = f"processing:{message.task_name}:{self._id}"
        await self._client.zrem(key, message.to_json())  # type: ignore
        if not drop:
            await self.publish(message, delay=delay)

    async def len(self, queue: str) -> int:
        return await self._client.zcard(f"queue:{queue}") or 0  # type: ignore

    async def clear(self, queue: str) -> None:
        await self._client.delete(f"queue:{queue}", f"processing:{queue}:{self._id}")  # type: ignore


class MemoryBroker(Broker):
    def __init__(self) -> None:
        self._queues: defaultdict[str, dict[str, float]] = defaultdict(dict)

    async def close(self) -> None:
        pass

    async def publish(
        self,
        message: Message,
        delay: float = 0,
    ) -> None:
        self._queues[message.task_name][message.to_json()] = time.time() + delay

    async def consume(self, queue: str) -> Message:
        while True:
            now = time.time()
            for msg, score in list(self._queues[queue].items()):
                if score <= now:
                    del self._queues[queue][msg]
                    return Message.from_json(msg)
            await asyncio.sleep(0.1)

    async def ack(self, message: Message) -> None:
        pass

    async def nack(
        self,
        message: Message,
        delay: float = 0,
        drop: bool = False,
    ) -> None:
        if not drop:
            await self.publish(message, delay=delay)

    async def len(self, queue: str) -> int:
        return len(self._queues[queue])

    async def clear(self, queue: str) -> None:
        self._queues.pop(queue, None)
