<p align="center">
  <img src="assets/logo.png" alt="LTQ" width="400">
</p>

<p align="center">
  A lightweight, Async-first task queue built on Redis.
</p>

## Installation

```bash
pip install ltq
# or
uv add ltq
```

## Quick Start

```python
import asyncio
import redis.asyncio as redis
import ltq

client = redis.from_url("redis://localhost:6379")
worker = ltq.Worker(client=client)

@worker.task()
async def send_email(to: str, subject: str, body: str) -> None:
    # your async code here
    pass

async def main():
    # Enqueue a task
    await send_email.send("user@example.com", "Hello", "World")

    # Or enqueue in bulk
    messages = [
        send_email.message("a@example.com", "Hi", "A"),
        send_email.message("b@example.com", "Hi", "B"),
    ]
    await send_email.send_bulk(messages)

asyncio.run(main())
```

Each task gets its own queue by default. To share a queue between tasks, pass `queue_name`:

```python
@worker.task(queue_name="emails")
async def send_email(...): ...

@worker.task(queue_name="emails")
async def send_newsletter(...): ...
```

## Running Workers

```bash
# Run a worker
ltq myapp:worker

# With options
ltq myapp:worker --concurrency 100 --log-level DEBUG
```

## Middleware

Add middleware to handle cross-cutting concerns:

```python
from ltq.middleware import Retry, RateLimit, Timeout

worker = ltq.Worker(
    client=client,
    middlewares=[
        Retry(max_retries=3, min_delay=1.0),
        RateLimit(requests_per_second=10),
        Timeout(timeout=30.0),
    ],
)
```

**Built-in:** `Retry`, `RateLimit`, `Timeout`, `Sentry` (requires `ltq[sentry]`)

**Custom middleware:**

```python
from ltq.middleware import Middleware, Handler
from ltq.message import Message

class Logger(Middleware):
    async def handle(self, message: Message, next_handler: Handler):
        print(f"Processing {message.task}")
        result = await next_handler(message)
        print(f"Completed {message.task}")
        return result
```
