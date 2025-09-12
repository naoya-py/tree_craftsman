import logging
import os
from logging.handlers import RotatingFileHandler


def configure_size_rotating_logger(
    log_path: str,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Configure and return a logger that uses RotatingFileHandler.

    - Creates parent directory if missing.
    - Ensures handler uses UTF-8 and a simple one-line formatter.
    """
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    logger = logging.getLogger("tree_craftsman")
    logger.setLevel(level)

    # Remove existing handlers for deterministic behavior in tests
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except OSError:
            pass

    handler = RotatingFileHandler(
        filename=log_path,
        mode="a",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=False,
    )

    # Minimal one-line formatter; in production replace with JSON renderer.
    fmt = (
        '%(asctime)s %(levelname)s %(name)s '
        '%(message)s'
    )
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    logger.addHandler(handler)
    logger.propagate = False
    return logger


def close_logger(logger: logging.Logger) -> None:
    """Close and remove handlers (test helper)."""
    for h in list(logger.handlers):
        try:
            h.flush()
            h.close()
        finally:
            logger.removeHandler(h)
