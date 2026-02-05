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

## Broker Backends

LTQ supports multiple broker backends:

- **Redis** (default): `broker_url="redis://localhost:6379"`
- **Memory**: `broker_url="memory://"` (useful for testing)

All workers and schedulers accept a `broker_url` parameter.

## Quick Start

```python
import asyncio
import ltq

worker = ltq.Worker("emails", broker_url="redis://localhost:6379")

@worker.task()
async def send_email(to: str, subject: str, body: str) -> None:
    # your async code here
    pass

async def main():
    # Enqueue a task
    await send_email.send("user@example.com", "Hello", "World")

    # Or enqueue multiple tasks
    for email in ["a@example.com", "b@example.com"]:
        await send_email.send(email, "Hi", "Message")

asyncio.run(main())
```

Each worker has a namespace (e.g., `"emails"`), and tasks are automatically namespaced as `{namespace}:{function_name}`.

## Running Workers

```bash
# Run a single worker
ltq run myapp:worker

# With options
ltq run myapp:worker --concurrency 100 --log-level DEBUG
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
ltq run --app myapp:app
```

### App Middleware

Apply middleware globally to all workers in an app:

```python
from ltq.middleware import Sentry

app = ltq.App(middlewares=[Sentry(dsn="https://...")])

# Or register after creation
app.register_middleware(Sentry(dsn="https://..."))
app.register_middleware(MyMiddleware(), pos=0)

# When workers are registered, app middlewares are prepended to each worker's stack
app.register_worker(emails_worker)
```

### Threading Model

By default, `App` runs each worker in its own thread with a separate event loop. This provides isolation between workers while keeping them in the same process. Workers won't block each other since each has its own async event loop.

**For maximum isolation** (separate memory, crash protection), run each worker in its own process:

```bash
# Terminal 1
ltq run myapp:emails_worker

# Terminal 2
ltq run myapp:notifications_worker
```

This gives you full process isolation at the cost of more overhead.

## Queue Management

Manage queues using the CLI:

```bash
# Clear a task queue
ltq clear emails:send_email

# Get queue size
ltq size emails:send_email

# With custom Redis URL
ltq clear emails:send_email --redis-url redis://localhost:6380
ltq size emails:send_email --redis-url redis://localhost:6380
```

Queue names are automatically namespaced as `{worker_name}:{function_name}`.

## Scheduler

Run tasks on a cron schedule (requires `ltq[scheduler]`):

```python
import ltq

scheduler = ltq.Scheduler()
scheduler.cron("*/5 * * * *", send_email.message("admin@example.com", "Report", "..."))
scheduler.start()  # Runs scheduler in blocking mode with asyncio.run()
```

## Task Options

Configure task behavior with options:

```python
from datetime import timedelta

@worker.task(max_tries=3, max_age=timedelta(hours=1), max_rate="10/s")
async def send_email(to: str, subject: str, body: str) -> None:
    # your async code here
    pass
```

**Available options:**

- `max_tries` (int): Maximum retry attempts before rejecting the message
- `max_age` (timedelta): Maximum message age before rejection
- `max_rate` (str): Rate limit in format `"N/s"`, `"N/m"`, or `"N/h"` (requests per second/minute/hour)

## Middleware

Middleware are async context managers that wrap task execution. The default stack is `[MaxTries(), MaxAge(), MaxRate()]`, so you only need to specify middlewares if you want to customize or add additional ones:

```python
from ltq.middleware import MaxTries, MaxAge, MaxRate, Sentry

worker = ltq.Worker(
    "emails",
    broker_url="redis://localhost:6379",
    middlewares=[
        MaxTries(),
        MaxAge(),
        MaxRate(),
        Sentry(dsn="https://..."),
    ],
)
```

**Built-in:** `MaxTries`, `MaxAge`, `MaxRate`, `Sentry` (requires `ltq[sentry]`)

You can also register middleware after creating the worker:

```python
worker.register_middleware(Sentry(dsn="https://..."))

# Insert at specific position (default is -1 for append)
worker.register_middleware(MyMiddleware(), pos=0)
```

**Custom middleware:**

```python
from contextlib import asynccontextmanager
from ltq.middleware import Middleware
from ltq.message import Message
from ltq.task import Task

class Logger(Middleware):
    @asynccontextmanager
    async def __call__(self, message: Message, task: Task):
        print(f"Processing {message.task_name}")
        yield
        print(f"Completed {message.task_name}")
```
