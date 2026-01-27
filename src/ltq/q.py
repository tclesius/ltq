from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .message import Message

if TYPE_CHECKING:
    from redis.asyncio import Redis


class Queue:
    _GET_SCRIPT = """
        local items = {}
        for i = 1, ARGV[1] do
            local item = redis.call("RPOP", KEYS[1])
            if not item then break end
            table.insert(items, item)
        end
        for i = 1, #items, 5000 do
            local chunk = {unpack(items, i, math.min(i + 4999, #items))}
            redis.call("SADD", KEYS[2], unpack(chunk))
        end
        return items
    """

    def __init__(self, client: Redis, name: str) -> None:
        self.client = client
        self.name = name
        self.queue_key = f"queue:{name}"
        self.processing_key = f"queue:{name}:processing"
        self._get = client.register_script(self._GET_SCRIPT)

    @staticmethod
    def _serialize(messages: list[Message]) -> list[str]:
        return [msg.to_json() for msg in messages]

    async def put(
        self,
        messages: list[Message],
        delay: float = 0.0,
        ttl: int | None = None,
    ) -> None:
        if not messages:
            return
        if delay > 0:
            await asyncio.sleep(delay)
        pipe = self.client.pipeline()
        for item in self._serialize(messages):
            pipe.lpush(self.queue_key, item)
        if ttl:
            pipe.expire(self.queue_key, ttl)
        await pipe.execute()  # type: ignore

    async def get(self, count: int) -> list[Message]:
        results = await self._get(
            keys=[self.queue_key, self.processing_key],
            args=[count],
        )  # type: ignore
        return [Message.from_json(r) for r in results]

    async def ack(self, messages: list[Message]) -> None:
        if not messages:
            return
        items = self._serialize(messages)
        await self.client.srem(self.processing_key, *items)  # type: ignore

    async def nack(self, messages: list[Message]) -> None:
        if not messages:
            return
        items = self._serialize(messages)
        pipe = self.client.pipeline()
        pipe.srem(self.processing_key, *items)
        for item in items:
            pipe.lpush(self.queue_key, item)
        await pipe.execute()  # type: ignore

    async def len(self) -> int:
        return await self.client.llen(self.queue_key)  # type: ignore

    async def clear(self) -> None:
        await self.client.delete(self.queue_key, self.processing_key)  # type: ignore
