import asyncio
import threading

from .middleware import Middleware
from .worker import Worker


class App:
    def __init__(self, middlewares: list[Middleware] | None = None) -> None:
        self.workers: dict[str, Worker] = dict()
        self.middlewares: list[Middleware] = middlewares or []

    def register_middleware(self, middleware: Middleware, pos: int = -1) -> None:
        if pos == -1:
            self.middlewares.append(middleware)
        else:
            self.middlewares.insert(pos, middleware)

    def register_worker(self, worker: Worker) -> None:
        if worker.name in self.workers:
            raise RuntimeError(f"Worker '{worker.name}' is already registered")
        worker.middlewares = list(self.middlewares) + worker.middlewares
        self.workers[worker.name] = worker

    @staticmethod
    def _run_worker(worker: Worker) -> None:
        asyncio.run(worker.run())

    async def run(self) -> None:
        threads: list[threading.Thread] = []
        for worker in self.workers.values():
            t = threading.Thread(target=self._run_worker, args=(worker,), daemon=True)
            t.start()
            threads.append(t)

        try:
            while any(t.is_alive() for t in threads):
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            # Allow graceful shutdown when the run coroutine is cancelled.
            pass
