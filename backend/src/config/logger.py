"""
Renvue Centralized Logging Engine.
Provides a standardized logger factory and root logger configuration
with dual handlers (formatted stdout stream and persistent file log).
"""

import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "../logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_INITIALIZED = False


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configures standard logging handlers for console and file output.
    Ensures consistent formatting across Uvicorn, Taskiq, and CLI workflows.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers if already present
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

    _INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """
    Standardized logger factory.
    Canonicalizes all logger names under the 'renvue' hierarchy:
      - __main__ -> renvue.main
      - agent.nodes -> renvue.agent.nodes
      - service.compliance -> renvue.service.compliance
    """
    setup_logging()
    clean_name = name.removeprefix("src.").removeprefix("renvue.")
    if clean_name in ["__main__", "main"]:
        full_name = "renvue.main"
    else:
        full_name = f"renvue.{clean_name}"

    return logging.getLogger(full_name)
