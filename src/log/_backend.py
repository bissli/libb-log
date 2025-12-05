"""Loguru backend - internal implementation detail.

This module is NOT part of the public API. Users should never import from here.
To switch backends, only this file needs to change.
"""
from __future__ import annotations

import logging
from typing import Any

from loguru import logger as _loguru

__all__ = ['get_backend', 'add_sink', 'remove_sink', 'complete', 'intercept_stdlib']


class InterceptHandler(logging.Handler):
    """Handler that intercepts stdlib logging and forwards to loguru.

    This allows existing code using logging.getLogger('job').info(...)
    to work transparently with the loguru backend.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding loguru level
        try:
            level = _loguru.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the log call originated
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Forward to loguru with proper depth for correct caller info
        _loguru.bind(logger_name=record.name).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


class LoguruBackend:
    """Loguru-based logging backend."""

    def __init__(self):
        self._sink_ids: list[int] = []
        self._configure_colors()

    def _configure_colors(self) -> None:
        """Configure custom level colors to match legacy behavior."""
        # DEBUG: purple/magenta, INFO: green, WARNING: yellow, ERROR/CRITICAL: red
        _loguru.level('DEBUG', color='<magenta>')
        _loguru.level('INFO', color='<green>')
        _loguru.level('WARNING', color='<yellow>')
        _loguru.level('ERROR', color='<red>')
        _loguru.level('CRITICAL', color='<red><bold>')

    def reset(self) -> None:
        """Remove all sinks and start fresh."""
        _loguru.remove()
        self._sink_ids.clear()
        self._configure_colors()  # Reapply colors after reset

    def log(
        self,
        level: str,
        msg: str,
        *args,
        context: dict | None = None,
        name: str | None = None,
        exc_info: bool = False,
        depth: int = 0,
        **kwargs,
    ) -> None:
        """Log a message at the given level."""
        bound = _loguru
        if context:
            bound = bound.bind(**context)
        if name:
            bound = bound.bind(logger_name=name)

        opt_kwargs = {'depth': depth + 2}  # Correct caller frame
        if exc_info:
            opt_kwargs['exception'] = True

        bound.opt(**opt_kwargs).log(level, msg, *args, **kwargs)

    def add_sink(self, sink: Any, **kwargs) -> int:
        """Add a sink and return its ID."""
        sink_id = _loguru.add(sink, **kwargs)
        self._sink_ids.append(sink_id)
        return sink_id

    def remove_sink(self, sink_id: int) -> None:
        """Remove a sink by ID."""
        _loguru.remove(sink_id)
        if sink_id in self._sink_ids:
            self._sink_ids.remove(sink_id)

    def configure(self, **kwargs) -> None:
        """Configure the logger (patchers, etc.)."""
        _loguru.configure(**kwargs)

    def complete(self) -> None:
        """Wait for all async sinks to complete."""
        _loguru.complete()


# Singleton backend instance
_backend: LoguruBackend | None = None


def get_backend() -> LoguruBackend:
    """Get the singleton backend instance."""
    global _backend
    if _backend is None:
        _backend = LoguruBackend()
    return _backend


# Module-level convenience functions for public API
def add_sink(sink: Any, **kwargs) -> int:
    """Add a sink. Returns sink ID for later removal."""
    return get_backend().add_sink(sink, **kwargs)


def remove_sink(sink_id: int) -> None:
    """Remove a sink by its ID."""
    get_backend().remove_sink(sink_id)


def complete() -> None:
    """Wait for all async sinks to complete. Call on shutdown."""
    get_backend().complete()


def intercept_stdlib(logger_names: list[str] | None = None) -> None:
    """Set up stdlib logging interception.

    After calling this, logging.getLogger('name').info(...) will be
    routed through loguru.

    Args:
        logger_names: Specific logger names to intercept. If None,
                      intercepts the root logger (all loggers).
    """
    # Set up root logger interception
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Also intercept specific named loggers if provided
    if logger_names:
        for name in logger_names:
            stdlib_logger = logging.getLogger(name)
            stdlib_logger.handlers = [InterceptHandler()]
            stdlib_logger.propagate = False
            stdlib_logger.setLevel(logging.DEBUG)  # Let loguru handle filtering
