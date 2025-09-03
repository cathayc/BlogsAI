"""Logging configuration for BlogsAI application."""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_level=logging.INFO):
    """Set up logging for the application."""
    # Get logs directory from distribution manager
    try:
        from ..config.distribution import get_distribution_manager

        dist_manager = get_distribution_manager()
        logs_dir = dist_manager.get_logs_directory()
    except ImportError:
        # Fallback for cases where distribution manager isn't available
        logs_dir = Path("data") / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"blogsai_{timestamp}.log"

    # Create formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_formatter = logging.Formatter("%(levelname)s - %(message)s")

    # Create handlers
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Log startup info
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Current working directory: {os.getcwd()}")

    return log_file


def setup_exception_logging():
    """Set up global exception handling."""

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger = logging.getLogger(__name__)
        logger.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception


def get_logger(name):
    """Get a logger instance."""
    return logging.getLogger(name)
