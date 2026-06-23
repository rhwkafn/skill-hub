"""Structured Logger — JSON-formatted, thread-safe, file+console logging with rotation."""

import json
import logging
import logging.handlers
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON lines."""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
            "process": record.process,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        if self.include_extra:
            standard_attrs = logging.LogRecord(
                "", 0, "", 0, "", (), None
            ).__dict__.keys()
            extra = {
                k: v
                for k, v in record.__dict__.items()
                if k not in standard_attrs and not k.startswith("_")
            }
            if extra:
                log_entry["extra"] = extra

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class StructuredLogger:
    """Thread-safe structured logger with JSON output, file rotation, and console support.

    Args:
        name: Logger name (used as the Python logger name).
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional file path for file-based logging.
        max_bytes: Max file size before rotation (default 10 MB).
        backup_count: Number of rotated backup files to keep (default 5).
        console: Whether to also log to stderr (default True).
        json_format: Whether to use JSON formatting for console output (default False).
    """

    _lock = threading.Lock()
    _instances: dict[str, "StructuredLogger"] = {}

    def __init__(
        self,
        name: str = "app",
        level: str = "INFO",
        log_file: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        console: bool = True,
        json_format: bool = False,
    ):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._logger.propagate = False

        if not self._logger.handlers:
            self._setup_handlers(
                log_file, max_bytes, backup_count, console, json_format
            )

    def _setup_handlers(
        self,
        log_file: Optional[str],
        max_bytes: int,
        backup_count: int,
        console: bool,
        json_format: bool,
    ) -> None:
        json_fmt = JSONFormatter()
        plain_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                str(path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(json_fmt)
            self._logger.addHandler(file_handler)

        if console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(json_fmt if json_format else plain_fmt)
            self._logger.addHandler(console_handler)

    @classmethod
    def get_logger(
        cls, name: str = "app", **kwargs
    ) -> "StructuredLogger":
        """Get or create a named StructuredLogger (singleton per name)."""
        with cls._lock:
            if name not in cls._instances:
                cls._instances[name] = cls(name=name, **kwargs)
            return cls._instances[name]

    def _log(self, level: int, message: str, **kwargs) -> None:
        self._logger.log(level, message, extra=kwargs or None)

    def debug(self, message: str, **kwargs) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log ERROR with current exception traceback."""
        self._logger.exception(message, extra=kwargs or None)

    @property
    def logger(self) -> logging.Logger:
        """Access the underlying stdlib logger."""
        return self._logger


def configure_root_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True,
) -> None:
    """Convenience: configure the root logger with JSON file output."""
    StructuredLogger(
        name="root",
        level=level,
        log_file=log_file,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console=console,
        json_format=False,
    )


# --- Demo / self-test ---
if __name__ == "__main__":
    logger = StructuredLogger.get_logger(
        "demo", level="DEBUG", log_file="demo.log", console=True
    )
    logger.info("Application started", version="1.0", env="dev")
    logger.debug("Debug details", user_id=42, action="login")
    logger.warning("Disk space low", free_pct=12.3)
    logger.error("Request failed", status=503, url="/api/data")
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Caught an exception")
    logger.critical("System shutting down")
    print("Done. Check demo.log for JSON output.")
