import io
import logging

__all__ = ['StderrStreamLogger']


class StderrStreamLogger:
    """Patch over stderr to log print statements to INFO.

    Placeholders isatty and fileno mimic python stream.
    stderr still accessible at stderr.__stderr__
    """

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.level = logging.INFO

    def write(self, buf: str) -> None:
        """Write buffer lines to logger.
        """
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def isatty(self) -> bool:
        """Return False as this is not a TTY.
        """
        return False

    def fileno(self) -> int:
        """Raise UnsupportedOperation as this is not a real file.
        """
        raise io.UnsupportedOperation('fileno')
