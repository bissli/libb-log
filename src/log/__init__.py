"""Logging library with loguru backend.

Public API - users should only import from this module.

Usage:
    import log

    # Configure logging for your setup type
    log.configure_logging('web', app='myapp')

    # Module-level logging
    log.info('Application started')
    log.error('Something failed')

    # Named/contextual loggers
    db_logger = log.get_logger('database')
    db_logger.debug('Query executed')

    # Add custom sinks
    log.add_sink(my_handler, level='ERROR')

    # stdlib logging still works (intercepted)
    import logging
    logger = logging.getLogger('web')
    logger.info('This also works!')
"""
from log._backend import add_sink, complete, remove_sink
from log._logger import Logger, get_logger
from log.loggers import StderrStreamLogger
from log.setup import SetupType, class_logger, configure_logging
from log.setup import log_exception, patch_webdriver, set_level

# Module-level logger instance
_module_logger: Logger | None = None


def _get_module_logger() -> Logger:
    """Get the module-level logger instance."""
    global _module_logger
    if _module_logger is None:
        _module_logger = Logger()
    return _module_logger


# Module-level convenience functions
def debug(msg: str, *args, **kwargs) -> None:
    """Log a debug message."""
    _get_module_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    """Log an info message."""
    _get_module_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    """Log a warning message."""
    _get_module_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    """Log an error message."""
    _get_module_logger().error(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs) -> None:
    """Log an error message with exception info."""
    _get_module_logger().exception(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    """Log a critical message."""
    _get_module_logger().critical(msg, *args, **kwargs)


# Aliases
warn = warning
fatal = critical


__all__ = [
    # Configuration
    'configure_logging',
    'set_level',
    'SetupType',
    # Logger access
    'get_logger',
    'Logger',
    # Logging methods
    'debug',
    'info',
    'warning',
    'warn',
    'error',
    'exception',
    'critical',
    'fatal',
    # Sink management
    'add_sink',
    'remove_sink',
    'complete',
    # Utilities
    'StderrStreamLogger',
    'patch_webdriver',
    'class_logger',
    'log_exception',
]
