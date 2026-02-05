"""CLI for running ltq workers."""

import asyncio
import importlib
import sys
from pathlib import Path
import argparse

from .logger import setup_logging, get_logger
from .app import App
from .broker import Broker
from .worker import Worker

logger = get_logger()


def import_from_string(import_str: str):
    """Import a Worker from 'module.path:worker_name'."""
    if ":" not in import_str:
        logger.error("Invalid format: %s", import_str)
        logger.error("Use: module:attribute")
        sys.exit(1)

    module_str, attr_str = import_str.split(":", 1)

    # Add cwd to path for local imports
    sys.path.insert(0, str(Path.cwd()))

    try:
        module = importlib.import_module(module_str)
        return getattr(module, attr_str)
    except ImportError as e:
        logger.error("Cannot import module '%s'", module_str)
        logger.error("%s", e)
        sys.exit(1)
    except AttributeError:
        logger.error("Module '%s' has no attribute '%s'", module_str, attr_str)
        sys.exit(1)


async def clear_queue(
    task_name: str,
    url: str = "redis://localhost:6379",
) -> None:
    """Clear a queue for a specific task."""
    broker = Broker.from_url(url)
    try:
        await broker.clear(task_name)
        logger.info(f"Cleared queue for task: {task_name}")
    finally:
        await broker.close()


async def get_queue_size(
    task_name: str,
    url: str = "redis://localhost:6379",
) -> int:
    """Get the size of a queue for a specific task."""
    broker = Broker.from_url(url)
    try:
        return await broker.len(task_name)
    finally:
        await broker.close()


def main():
    """Run a ltq worker."""

    parser = argparse.ArgumentParser(
        prog="ltq",
        description="Run a ltq worker or manage queues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  ltq run examples:worker --concurrency 100\n  ltq clear emails:send_email",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a worker or app")
    run_parser.add_argument(
        "worker", nargs="?", help="Worker import string (module:attribute)"
    )
    run_parser.add_argument(
        "--app", dest="app", help="App import string (module:attribute)"
    )
    run_parser.add_argument(
        "--concurrency", type=int, help="Override worker concurrency"
    )
    run_parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)",
    )

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear a task queue")
    clear_parser.add_argument("task_name", help="Task name (namespace:function)")
    clear_parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379",
        help="Redis URL (default: redis://localhost:6379)",
    )
    clear_parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)",
    )

    # Size command
    size_parser = subparsers.add_parser("size", help="Get queue size for a task")
    size_parser.add_argument("task_name", help="Task name (namespace:function)")
    size_parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379",
        help="Redis URL (default: redis://localhost:6379)",
    )

    args = parser.parse_args()

    # Setup colored logging for CLI
    setup_logging(level=getattr(args, "log_level", "INFO"))
    if hasattr(args, "log_level") and args.log_level:
        logger.setLevel(args.log_level)

    # Handle clear command
    if args.command == "clear":
        asyncio.run(clear_queue(args.task_name, args.redis_url))
        return

    # Handle size command
    if args.command == "size":
        size = asyncio.run(get_queue_size(args.task_name, args.redis_url))
        print(f"{args.task_name}: {size}")
        return

    # Handle run command
    if args.command == "run":
        if not args.worker and not args.app:
            run_parser.error("either worker or --app is required")
        if args.worker and args.app:
            run_parser.error("cannot specify both worker and --app")

        if args.app:
            app: App = import_from_string(args.app)

            for w in app.workers.values():
                if args.concurrency:
                    w.concurrency = args.concurrency

            logger.info("Starting ltq app")

            try:
                asyncio.run(app.run())
            except KeyboardInterrupt:
                logger.info("Shutting down...")
        else:
            worker: Worker = import_from_string(args.worker)

            if args.concurrency:
                worker.concurrency = args.concurrency

            logger.info("Starting ltq worker")

            try:
                asyncio.run(worker.run())
            except KeyboardInterrupt:
                logger.info("Shutting down...")
        return

    # No command specified
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
