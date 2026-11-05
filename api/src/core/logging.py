import logging
from logging.config import dictConfig


def configure_logging(level: str) -> None:
    """Send all logs, including Uvicorn's, to stdout in one format."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"level": level.upper(), "handlers": ["console"]},
            "loggers": {
                # Uvicorn's loggers pass their records up to the root logger.
                "uvicorn": {"handlers": [], "propagate": True},
                "uvicorn.error": {"handlers": [], "propagate": True},
                "uvicorn.access": {"handlers": [], "propagate": True},
            },
        }
    )
    logging.getLogger(__name__).debug("Logging configured at %s", level.upper())
