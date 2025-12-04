import logging
import socket
from collections.abc import Callable

__all__ = [
    'MachineFilter',
    'PreambleFilter',
    'WebServerFilter',
    ]


class MachineFilter(logging.Filter):
    """Simple filter that adds socket hostname to records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add machine hostname to record.
        """
        record.machine = socket.gethostname()
        return True


class PreambleFilter(logging.Filter):
    """Filter that adds preamble metadata to records.
    """

    def __init__(self, app: str = '', args: str = '', setup: str = '',
                 statuses: tuple[str, str] = ('succeeded', 'failed'),
                 failno: int = 40) -> None:
        self.cmd_app = app
        self.cmd_args = args
        self.cmd_setup = setup
        self._success, self._failure = statuses
        self.cmd_status = self._success
        self.failno = failno

    def filter(self, record: logging.LogRecord) -> bool:
        """Add preamble metadata to record.
        """
        record.cmd_app = self.cmd_app
        record.cmd_args = self.cmd_args
        record.cmd_setup = self.cmd_setup
        if record.levelno >= self.failno:
            self.cmd_status = self._failure
        record.cmd_status = self.cmd_status
        return True


class WebServerFilter(logging.Filter):
    """Filter that adds wsgi webserver context info to records.

    >>> import web  # doctest: +SKIP
    >>> ip_fn = lambda: web.ctx.get('ip')  # doctest: +SKIP
    >>> user_fn = lambda: web.ctx.session.get('user')  # doctest: +SKIP
    >>> handler.addFilter(WebServerFilter(ip_fn, user_fn))  # doctest: +SKIP

    >>> import flask  # doctest: +SKIP
    >>> ip_fn = lambda: flask.request.remote_addr  # doctest: +SKIP
    >>> user_fn = lambda: flask.session.get('user')  # doctest: +SKIP
    >>> handler.addFilter(WebServerFilter(ip_fn, user_fn))  # doctest: +SKIP
    """

    def __init__(self, ip_fn: Callable[[], str] = lambda: '',
                 user_fn: Callable[[], str] = lambda: '') -> None:
        self.ip_fn = ip_fn
        self.user_fn = user_fn

    def filter(self, record: logging.LogRecord) -> bool:
        """Add IP and user to record.
        """
        ipaddr = self.ip_fn() or ''
        if not ipaddr:
            record.ip = ipaddr
        else:
            try:
                hostname, aliases, _ = socket.gethostbyaddr(ipaddr)
            except OSError:
                hostname = ipaddr
            record.ip = hostname
        record.user = self.user_fn() or ''
        return True


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
