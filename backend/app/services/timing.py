"""Content-free timing records through the application's Uvicorn log handler."""
import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Iterator

logger = logging.getLogger("uvicorn.error.solvo.timing")


@contextmanager
def timed(stage: str) -> Iterator[None]:
    started = perf_counter()
    outcome = "error"
    try:
        yield
        outcome = "success"
    finally:
        duration_ms = (perf_counter() - started) * 1000
        logger.info(
            "stage=%s duration_ms=%.2f outcome=%s", stage, duration_ms, outcome,
            extra={"stage": stage, "duration_ms": duration_ms, "outcome": outcome},
        )
