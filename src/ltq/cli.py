"""CLI for running ltq workers."""

import asyncio
import importlib
import sys
from pathlib import Path
import argparse

from .logger import setup_logging, get_logger
from .app import App
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


def main():
    """Run a ltq worker."""

    parser = argparse.ArgumentParser(
        prog="ltq",
        description="Run a ltq worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  ltq example:worker --concurrency 100",
    )

    parser.add_argument(
        "worker", nargs="?", help="Worker import string (module:attribute)"
    )
    parser.add_argument(
        "--app", dest="app", help="App import string (module:attribute)"
    )
    parser.add_argument("--concurrency", type=int, help="Override worker concurrency")
    parser.add_argument("--poll-sleep", type=float, help="Override worker poll sleep")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)",
    )
    args = parser.parse_args()

    if not args.worker and not args.app:
        parser.error("either worker or --app is required")
    if args.worker and args.app:
        parser.error("cannot specify both worker and --app")

    # Setup colored logging for CLI
    setup_logging(level=args.log_level)
    if args.log_level:
        logger.setLevel(args.log_level)

    if args.app:
        app: App = import_from_string(args.app)

        for w in app.workers:
            if args.concurrency:
                w.concurrency = args.concurrency
            if args.poll_sleep:
                w.poll_sleep = args.poll_sleep

        logger.info("Starting ltq app")
        logger.info("App: %s (%d workers)", args.app, len(app.workers))

        try:
            asyncio.run(app.run())
        except KeyboardInterrupt:
            logger.info("Shutting down...")
    else:
        worker: Worker = import_from_string(args.worker)

        if args.concurrency:
            worker.concurrency = args.concurrency
        if args.poll_sleep:
            worker.poll_sleep = args.poll_sleep

        logger.info("Starting ltq worker")
        logger.info("Worker: %s", args.worker)

        try:
            asyncio.run(worker.run())
        except KeyboardInterrupt:
            logger.info("Shutting down...")


if __name__ == "__main__":
    main()
