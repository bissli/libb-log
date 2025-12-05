"""Logger facade - abstracts the underlying logging implementation.

Users interact with this module, never with loguru directly.
"""
from __future__ import annotations

__all__ = ['Logger', 'get_logger']


class Logger:
    """Logging facade - abstracts the underlying implementation.

    Users interact with this class, never with loguru directly.
    Backend can be swapped without changing consumer code.
    """

    def __init__(self, name: str | None = None, **context):
        self._name = name
        self._context = context

    def bind(self, **kwargs) -> Logger:
        """Return a new logger with additional context."""
        new_context = {**self._context, **kwargs}
        return Logger(name=self._name, **new_context)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log('DEBUG', msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log('INFO', msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log('WARNING', msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log('ERROR', msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log error with exception info."""
        self._log('ERROR', msg, *args, exc_info=True, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._log('CRITICAL', msg, *args, **kwargs)

    # Aliases
    warn = warning
    fatal = critical

    def _log(self, level: str, msg: str, *args, exc_info: bool = False, **kwargs) -> None:
        from log._backend import get_backend
        get_backend().log(
            level, msg, *args,
            context=self._context,
            name=self._name,
            exc_info=exc_info,
            depth=1,  # Account for this wrapper
            **kwargs
        )


# Global default logger instance
_default_logger: Logger | None = None


def get_logger(name: str | None = None, **context) -> Logger:
    """Get a logger instance, optionally with a name and context.

    Args:
        name: Logger name (appears in logs as logger_name)
        **context: Additional context to bind to all log messages

    Returns
        Logger instance

    Examples
        >>> log = get_logger('mymodule')
        >>> log.info('Hello')

        >>> log = get_logger(user='john', request_id='abc123')
        >>> log.info('Processing request')
    """
    return Logger(name=name, **context)


def _get_default_logger() -> Logger:
    """Get the default logger instance (lazy initialization)."""
    global _default_logger
    if _default_logger is None:
        _default_logger = Logger()
    return _default_logger
