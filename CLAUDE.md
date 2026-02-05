# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LTQ is a lightweight, async-first task queue built on Redis. It uses a middleware pattern implemented as async context managers for cross-cutting concerns like retries, rate limiting, and error tracking.

## Commands

```bash
# Install dependencies
uv sync

# Run a single worker
ltq run examples.github:worker

# Run with options
ltq run examples.github:worker --concurrency 100 --log-level DEBUG

# Run an App (multiple workers in threads)
ltq run --app examples.app.main:app

# Clear a queue
ltq clear github:fetch

# Get queue size
ltq size github:fetch

# Run the example script (enqueue tasks)
python examples/github.py

# Run scheduled tasks example
python examples/scheduled.py

# Enqueue tasks for app example
python examples/app/main.py
```

## Examples

- **examples/github.py**: Single worker with rate limiting and retries for fetching GitHub repo data
- **examples/scheduled.py**: Cron-based task scheduling with two alternating tasks
- **examples/multithreading.py**: Demonstrates CPU-bound task parallelism using asyncio.to_thread
- **examples/app/**: Multi-worker app example with separate workers for emails and notifications
  - `examples/app/main.py`: App configuration and task enqueuing script
  - `examples/app/emails.py`: Email worker
  - `examples/app/notifications.py`: Notifications worker

## Architecture

### Broker Abstraction

The `Broker` class provides a unified interface for message queuing with multiple backend implementations:

- **RedisBroker**: Production-ready, persistent queue using Redis sorted sets
- **MemoryBroker**: In-memory queue for testing and development

Create a broker with `Broker.from_url(url)` which automatically selects the implementation based on the URL scheme (`redis://` or `memory://`).

### Message Flow

1. `Task.send()` serializes args/kwargs into a `Message` and publishes to broker (Redis sorted set or memory)
2. `Worker` polls queues continuously via `broker.consume()`, one message at a time
3. Each message is processed concurrently (up to `concurrency` limit via semaphore)
4. Messages pass through the middleware chain as async context managers (using `AsyncExitStack`)
5. The innermost layer executes the actual task function
6. Messages are acknowledged after successful processing; `RetryError` triggers re-enqueue with delay via `broker.nack()`

### Key Components

- **Worker** (`worker.py`): Orchestrates task execution. Registers tasks via `@worker.task()` decorator, builds middleware chain, handles concurrency. Constructor signature: `Worker(name, broker_url="redis://localhost:6379", concurrency=100, middlewares=None)`
- **App** (`app.py`): Runs multiple workers in separate threads with isolated event loops. Each worker gets its own thread for isolation while staying in the same process. App can have its own middleware that gets prepended to each registered worker's middleware stack
- **Broker** (`broker.py`): Abstract queue interface with two implementations:
  - `RedisBroker`: Redis-backed using sorted sets for time-based message retrieval. Supports delayed messages.
    - `queue:{name}` - sorted set with task messages, scored by execution time
    - `processing:{name}:{worker_id}` - sorted set tracking in-flight messages
  - `MemoryBroker`: In-memory broker for testing (use `broker_url="memory://"`)
- **Middleware** (`middleware.py`): Abstract base as async context manager. Built-ins: `MaxTries`, `MaxAge`, `MaxRate`, `Sentry`
- **Message** (`message.py`): Dataclass with `args`, `kwargs`, `task_name`, `ctx` (context dict for middleware state), `id`
- **Task** (`task.py`): Wraps async functions. Provides `send(*args, **kwargs)` and `message(*args, **kwargs)` methods. `send()` returns None (previously returned message id)
- **Scheduler** (`scheduler.py`): Cron-based task scheduling using `croniter`. Use `scheduler.start()` to run in blocking mode or `scheduler.start_background()` for async background task
- **Utils** (`utils.py`): Currently empty - the `dispatch()` function was removed. Use task.send() in a loop instead

### Task Options

Tasks can be configured with options passed to `@worker.task()`:

```python
@worker.task(max_tries=3, max_age=timedelta(hours=1), max_rate="10/s")
async def my_task(...): ...
```

- `max_tries` (int): Maximum retry attempts
- `max_age` (timedelta): Maximum message age before rejection
- `max_rate` (str): Rate limit in format `"N/s"`, `"N/m"`, or `"N/h"`

### Middleware Pattern

Middleware are async context managers that wrap task execution:

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator
from ltq.middleware import Middleware
from ltq.message import Message
from ltq.task import Task

class MyMiddleware(Middleware):
    @asynccontextmanager
    async def __call__(self, message: Message, task: Task) -> AsyncIterator[None]:
        # Before task execution (setup, validation, rate limiting, etc.)
        print(f"Starting {message.task_name}")
        try:
            yield  # Task execution happens here
            # After successful task execution (cleanup, logging, etc.)
            print(f"Completed {message.task_name}")
        except Exception:
            # Handle errors, decide whether to retry or reject
            raise
```

**Key points:**

- Use `message.ctx` to store state across retries or pass data between middleware
- Raise `RetryError(delay=seconds)` to re-enqueue with delay
- Raise `RejectError(reason)` to drop the message permanently
- Default middleware stack: `[MaxTries(), MaxAge(), MaxRate()]`
- Register middleware via `Worker.__init__(middlewares=[...])` or `worker.register_middleware(middleware, pos=-1)`
- Middleware execution uses `AsyncExitStack` for proper context manager lifecycle

### Error Handling

- `RetryError(delay=float)`: Caught by worker, message re-enqueued with specified delay via `broker.nack(message, delay=delay)`
- `RejectError(reason)`: Message is acknowledged and dropped (logged as warning), via `broker.nack(message, drop=True)`
- Other exceptions: Logged as errors, message dropped via `broker.nack(message, drop=True)`

Note: The default behavior for unhandled exceptions is to drop the message after logging. Use middleware like `MaxTries` with task options to enable retries.

### Threading Model (App)

`App` runs each registered worker in its own thread with a separate event loop. This provides:

- Isolation between workers (one worker's blocking operation won't affect others)
- Shared process (easier deployment than separate processes)
- Independent event loops (each worker has its own async context)

**App Middleware:**

- App can have its own middleware via `App.__init__(middlewares=[...])` or `app.register_middleware(middleware, pos=-1)`
- When `app.register_worker(worker)` is called, the app's middlewares are prepended to the worker's middleware stack
- This allows global middleware (like Sentry) to be applied to all workers in the app

For maximum isolation (separate memory, crash protection), run workers in separate processes instead.
