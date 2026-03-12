import logging
import sys
from typing import Any

import orjson
import structlog

from app.core.config import settings


def setup_logging() -> None:
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.dev.set_exc_info,
    ]
    if settings.debug_mode:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.dict_tracebacks)
        processors.append(structlog.processors.JSONRenderer(serializer=orjson.dumps))
    structlog.configure(
        processors=processors, logger_factory=structlog.stdlib.LoggerFactory()
    )
    logging.basicConfig(format='%(message)s', stream=sys.stdout, level=logging.INFO)
