
import logging
import os
from logging.handlers import RotatingFileHandler

COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[41m",  # Red background
    "RESET": "\033[0m",
}

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        levelname = record.levelname
        if levelname in COLORS:
            levelname_color = COLORS[levelname] + levelname + COLORS["RESET"]
            record.levelname = levelname_color
        return super().format(record)

def setup_logger(log_file, logger_name, level=logging.INFO):
    log_dir = os.path.dirname(log_file)
    if log_dir != '': os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.propagate = False
    logger.setLevel(level)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(module)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(
        "%(asctime)s - %(levelname)s - %(module)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

#logger = setup_logger("logs/name.log")
