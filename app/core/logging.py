# app/core/logging.py

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class SafeRotatingFileHandler(RotatingFileHandler):
    """Keep logging if Windows blocks rollover because another process owns the file."""

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except PermissionError:
            if self.stream:
                self.stream.close()
                self.stream = None
            if not self.delay:
                self.stream = self._open()
        except OSError as exc:
            if getattr(exc, "winerror", None) != 32:
                raise
            if self.stream:
                self.stream.close()
                self.stream = None
            if not self.delay:
                self.stream = self._open()


def configure_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    file_handler = SafeRotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=1_000_000,   # 1 MB
        backupCount=3,        # app.log.1, app.log.2, app.log.3
        encoding="utf-8",
    )

    console_handler = logging.StreamHandler(sys.stdout)

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            console_handler,
            file_handler,
        ],
        force=True,  # important if logging was already configured
    )

    for dependency_logger in ("httpx", "httpcore"):
        logging.getLogger(dependency_logger).setLevel(logging.WARNING)
