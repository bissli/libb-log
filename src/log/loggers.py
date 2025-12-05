"""Stream loggers for capturing output."""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from log._logger import Logger

__all__ = ['StderrStreamLogger']


class StderrStreamLogger:
    """Patch over stderr to log print statements to INFO.

    Placeholders isatty and fileno mimic python stream.
    stderr still accessible at stderr.__stderr__

    Works with both stdlib logging.Logger and facade Logger instances.
    """

    def __init__(self, logger: logging.Logger | Logger | Any) -> None:
        self.logger = logger
        self.level = logging.INFO

    def write(self, buf: str) -> None:
        """Write buffer lines to logger."""
        for line in buf.rstrip().splitlines():
            msg = line.rstrip()
            # Support both stdlib Logger.log(level, msg) and facade Logger.info(msg)
            if hasattr(self.logger, 'log') and callable(getattr(self.logger, 'log', None)):
                # stdlib logging.Logger
                self.logger.log(self.level, msg)
            else:
                # facade Logger - use info() directly
                self.logger.info(msg)

    def isatty(self) -> bool:
        """Return False as this is not a TTY.
        """
        return False

    def fileno(self) -> int:
        """Raise UnsupportedOperation as this is not a real file.
        """
        raise io.UnsupportedOperation('fileno')
