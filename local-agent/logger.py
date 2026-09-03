import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_DIR, LOG_MODE

_cleared_paths = set()


def _maybe_clear_log(path):
    if LOG_MODE != "clear":
        return
    if path in _cleared_paths:
        return
    try:
        if path.exists():
            with open(path, "w", encoding="utf-8"):
                pass
        _cleared_paths.add(path)
    except OSError:
        pass


def build_logger(name: str) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "local-agent.log"
    _maybe_clear_log(log_path)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def build_agent_output_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "agent-output.log"
    _maybe_clear_log(log_path)

    logger = logging.getLogger("agent_output")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    file_handler = logging.FileHandler(
        log_path,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

    logger.addHandler(file_handler)
    return logger
