import asyncio

from .worker import Worker


class App:
    def __init__(self) -> None:
        self.workers: set[Worker] = set()

    def register_worker(self, worker: Worker) -> None:
        self.workers.add(worker)

    async def run(self) -> None:
        await asyncio.gather(*(w.run() for w in self.workers))
