# app/core/logging.py

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    file_handler = RotatingFileHandler(
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