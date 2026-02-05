import logging
import sys
import threading


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored severity levels."""

    # ANSI color codes
    RESET = "\033[0m"
    GRAY = "\033[90m"
    GREEN = "\033[32m"
    BRIGHT_GREEN = "\033[92m"
    YELLOW = "\033[33m"
    RED = "\033[91m"
    CYAN = "\033[36m"

    COLORS = {
        logging.DEBUG: GRAY,
        logging.INFO: BRIGHT_GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colored severity level."""
        color = self.COLORS.get(record.levelno, self.RESET)
        log_time = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        log_time_ms = f"{log_time}.{int(record.msecs):03d}"
        timestamp = f"{self.GRAY}{log_time_ms}{self.RESET}"

        levelname = f"{color}{record.levelname:<4}{self.RESET}"

        name = record.name.removeprefix("ltq.")
        workername = f"{self.CYAN}{name:<6}{self.RESET}"
        thread_id = f"{self.GRAY}[{threading.current_thread().ident}]{self.RESET}"

        message = record.getMessage()
        log_line = f"{timestamp} {thread_id} {levelname} {workername} {message}"

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            lines = record.exc_text.split("\n")
            log_line += "\n" + "\n".join(
                f"  {self.GRAY}{line}{self.RESET}" for line in lines
            )

        return log_line


def setup_logging(level: int | str = logging.INFO) -> None:
    logger = logging.getLogger("ltq")

    if not logger.handlers:
        logger.setLevel(level)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)

        logger.propagate = False


def get_logger(name: str = "ltq") -> logging.Logger:
    if name == "ltq":
        return logging.getLogger("ltq")
    return logging.getLogger(f"ltq.{name}")
