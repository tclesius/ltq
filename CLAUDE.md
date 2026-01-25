# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LTQ is a lightweight, async-first task queue built on Redis. It uses a middleware pattern for cross-cutting concerns like retries, rate limiting, and error tracking.

## Commands

```bash
# Install dependencies
uv sync

# Run a worker
uv run ltq examples.github:worker

# Run with options
uv run ltq examples.github:worker --concurrency 100 --log-level DEBUG

# Run the example script (enqueue tasks)
uv run python examples/github.py
```

## Architecture

### Message Flow

1. `Task.send()` serializes args/kwargs into a `Message` and pushes to Redis queue
2. `Worker` polls queues and retrieves batches of messages (up to `concurrency` count)
3. Messages pass through the middleware chain (applied in reverse order via `functools.partial`)
4. The innermost handler executes the actual task function
5. Messages are acknowledged after processing; `RetryMessage` exceptions trigger re-enqueue with delay

### Key Components

- **Worker** (`worker.py`): Orchestrates task execution. Registers tasks via `@worker.task()` decorator, builds middleware chain, handles concurrency
- **Queue** (`q.py`): Redis-backed queue using Lua scripts for atomic get-and-mark-processing. Maintains `queue:{name}` list and `queue:{name}:processing` set
- **Middleware** (`middleware.py`): Abstract base with `async handle(message, next_handler)`. Built-ins: `Retry`, `RateLimit`, `Timeout`, `Sentry`
- **Message** (`message.py`): Dataclass with `args`, `kwargs`, `task`, `ctx` (context dict for middleware state), `id`
- **Task** (`task.py`): Wraps async functions. Provides `send()`, `send_bulk()`, and `message()` methods

### Middleware Pattern

```python
class Middleware(ABC):
    @abstractmethod
    async def handle(self, message: Message, next_handler: Handler) -> Any: ...
```

- Use `message.ctx` to store state across retries or pass data between middleware
- Raise `RetryMessage(delay, reason)` to re-enqueue with delay
- Raise `RejectMessage()` to drop the message
- Middlewares wrap each other; outermost runs first, innermost calls the task function

### Error Handling

- `RetryMessage`: Caught by worker, message re-enqueued with specified delay
- `RejectMessage`: Defined but not currently handled specially by worker (message gets acked)
- Other exceptions: Logged as errors, message still acknowledged
