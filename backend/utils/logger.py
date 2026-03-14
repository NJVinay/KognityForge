"""Step-by-step execution logger for the workflow orchestrator."""

import logging
import time
from contextlib import contextmanager
from typing import Generator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("kognityforge")


@contextmanager
def step_timer(step_name: str) -> Generator[dict, None, None]:
    """Context manager that logs and times a workflow step.

    Yields a mutable dict where callers can stash ``tokens`` and ``status``.

    Usage::

        with step_timer("planner") as ctx:
            result = call_llm(...)
            ctx["tokens"] = result.usage.total_tokens
    """
    info: dict = {"step": step_name, "tokens": 0, "status": "success"}
    logger.info("▶  %s – started", step_name)
    start = time.perf_counter()
    try:
        yield info
    except Exception as exc:
        info["status"] = "failed"
        info["error"] = str(exc)
        logger.error("✗  %s – failed: %s", step_name, exc)
        raise
    finally:
        elapsed = time.perf_counter() - start
        info["duration"] = round(elapsed, 3)
        symbol = "✓" if info["status"] == "success" else "✗"
        logger.info(
            "%s  %s – %ss  (tokens: %d)",
            symbol,
            step_name,
            info["duration"],
            info["tokens"],
        )
