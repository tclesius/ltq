<p align="center">
  <img src="https://raw.githubusercontent.com/tclesius/ltq/refs/heads/main/assets/logo.png" alt="LTQ" width="400">
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
import ltq

worker = ltq.Worker(url="redis://localhost:6379")

@worker.task()
async def send_email(to: str, subject: str, body: str) -> None:
    # your async code here
    pass

async def main():
    # Enqueue a task
    await send_email.send("user@example.com", "Hello", "World")

    # Or dispatch in bulk
    messages = [
        send_email.message("a@example.com", "Hi", "A"),
        send_email.message("b@example.com", "Hi", "B"),
    ]
    await ltq.dispatch(messages)

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
# Run a single worker
ltq myapp:worker

# With options
ltq myapp:worker --concurrency 100 --log-level DEBUG
```

## Running an App

Register multiple workers into an `App` to run them together:

```python
import ltq

app = ltq.App()
app.register_worker(emails_worker)
app.register_worker(notifications_worker)
```

```bash
ltq --app myapp:app
```

## Scheduler

Run tasks on a cron schedule (requires `ltq[scheduler]`):

```python
import ltq

scheduler = ltq.Scheduler()
scheduler.cron("*/5 * * * *", send_email.message("admin@example.com", "Report", "..."))
scheduler.run()
```

## Middleware

Add middleware to handle cross-cutting concerns:

```python
from ltq.middleware import Retry, RateLimit, Timeout

worker = ltq.Worker(
    url="redis://localhost:6379",
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
