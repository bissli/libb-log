"""TODO:
- Hander: 'twd_mail' - using defer() in the handler
"""
import base64
import copy
import logging
import platform
import smtplib
import sys
import urllib.request
from contextlib import closing, suppress
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from functools import wraps
from logging.handlers import HTTPHandler, SMTPHandler
from typing import Any
from collections.abc import Callable

from libb import stream_is_tty
from log.colors import choose_color_ansi, choose_color_windows, set_color
from log.filters import PreambleFilter

with suppress(ImportError):
    from twisted.internet import reactor
    from twisted.internet.defer import Deferred
    from twisted.internet.ssl import SSL, ClientContextFactory
    from twisted.mail.smtp import ESMTPSenderFactory

with suppress(ImportError):
    import boto3

with suppress(ImportError):
    import mailchimp_transactional as MailchimpTransactional

__all__ = [
    'BufferedColoredSMTPHandler',
    'ColoredHandler',
    'ColoredMandrillHandler',
    'ColoredSMTPHandler',
    'ColoredStreamHandler',
    'NonBufferedFileHandler',
    'ScreenshotColoredMandrillHandler',
    'ScreenshotColoredSMTPHandler',
    'TwistedSMTPHandler',
    'URLHandler',
    'SNSHandler',
    ]


def colorize(f: Callable[..., None]) -> Callable[..., None]:
    """Decorator that converts stream to colored output, cross-platform.
    """
    @wraps(f)
    def wrapper(*args: Any) -> None:
        logger = args[0]
        record = copy.copy(args[1])
        other_args = args[2:] if len(args) > 2 else []
        levelno = record.levelno
        if not logger.is_tty:
            return f(logger, record, *other_args)
        if 'Win' in platform.system():
            color = choose_color_windows(levelno)
        else:
            color = choose_color_ansi(levelno)
        with set_color(color, stream=logger.stream):
            return f(logger, record, *other_args)
    return wrapper


class NonBufferedFileHandler(logging.FileHandler):
    """Non-buffered version of the standard FileHandler.

    Closes and reopens the file for each emit.
    Adds a preamble if PreambleFilter is enabled.
    """

    def __init__(self, filename: str, mode: str = 'a', encoding: str | None = None,
                 delay: bool = False) -> None:
        super().__init__(filename, mode, encoding, delay)
        self.mode = mode
        self.encoding = encoding
        self.preamble = ('***********************\n'
                         '** Time:  %(asctime)s\n'
                         '** App:   %(cmd_app)s\n'
                         '** Args:  %(cmd_args)s\n'
                         '** Setup: %(cmd_setup)s\n'
                         '***********************\n')

    def emit(self, record: logging.LogRecord) -> None:
        if self.stream:
            self.stream.close()
        with self._open() as handle:
            self.stream = handle
            if any(isinstance(f, PreambleFilter) for f in self.filters):
                if not hasattr(record, 'asctime'):
                    record.asctime = self.formatter.formatTime(record) if self.formatter else logging.Formatter().formatTime(record)
                self.stream.write(self.preamble % record.__dict__)
            super().emit(record)


class ColoredStreamHandler(logging.StreamHandler):
    """Coloring stream handler in logging module.
    """

    def __init__(self) -> None:
        super().__init__()

    @property
    def is_tty(self) -> bool:
        """No need to colorize output to other processes.
        """
        return stream_is_tty(self.stream)

    @property
    def std_or_stderr(self) -> bool:
        """Check if stream is stdout or stderr.
        """
        fileno = getattr(self.stream, 'fileno', None)
        return fileno and fileno() in {sys.stdout.fileno(), sys.stderr.fileno()}

    @colorize
    def emit(self, record: logging.LogRecord) -> None:
        """Call parent StreamHandler emit after colorizing.
        """
        super().emit(record)


class ColoredHandler:
    """Mixin for any logging.Handler trying to generate text and html messages.
    """
    subject: str

    def getSubject(self, record: logging.LogRecord) -> str:
        """Get formatted subject from record.
        """
        subject = self.subject % record.__dict__
        return subject

    def _format_record(self, record: logging.LogRecord) -> tuple[str, str]:
        """Format record as text and HTML.
        """
        color = self._choose_color_html(record.levelno)
        text = self.format(record)
        html = f'<pre style="color:{color};">{text}</pre>'
        return text, html

    def _choose_color_html(self, levelno: int) -> str:
        """Choose HTML color based on log level.
        """
        if levelno >= 40:
            color = '#EE0000'
        elif levelno >= 30:
            color = '#DAA520'
        elif levelno >= 20:
            color = '#228B22'
        elif levelno >= 10:
            color = '#D0D2C4'
        else:
            color = '#000'
        return color


class ColoredSMTPHandler(ColoredHandler, SMTPHandler):
    """Emits html-colored email, one per log message.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.ssl = kwargs.pop('ssl', False)
        super().__init__(*args, **kwargs)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self._build_html_msg(record)
            text, html = self._format_record(record)
            html = f'<html><head></head><body>{html}</body></html>'
            msg.attach(MIMEText(text, 'text'))
            msg.attach(MIMEText(html, 'html'))
            self._send_html_msg(msg.as_string())
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

    def _build_html_msg(self, record: logging.LogRecord) -> MIMEMultipart:
        """Build MIME multipart message from record.
        """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.getSubject(record)
        msg['From'] = self.fromaddr
        msg['To'] = ','.join(self.toaddrs)
        msg['Date'] = formatdate()
        return msg

    def _send_html_msg(self, msg: str) -> None:
        """Send HTML message via SMTP.
        """
        port = self.mailport
        if not port:
            port = smtplib.SMTP_PORT
        if self.ssl:
            smtp = smtplib.SMTP_SSL(self.mailhost, port)
        else:
            smtp = smtplib.SMTP(self.mailhost, port)
        if self.secure is not None:
            smtp.ehlo()
            smtp.starttls(*self.secure)
            smtp.ehlo()
        if self.username:
            smtp.login(self.username, self.password)
        smtp.sendmail(self.fromaddr, self.toaddrs, msg)
        smtp.quit()


class TwistedSMTPHandler:
    """Twisted mixin to make a deferred version of our SMTPHandlers.
    """

    def _send_html_msg(self, msg: str) -> Any:
        """Send HTML message via Twisted deferred SMTP.
        """
        port = self.mailport
        if not port:
            port = smtplib.SMTP_PORT
        dfd = Deferred()
        kw = {}
        if self.ssl:
            kw['contextFactory'] = ClientContextFactory()
            kw['contextFactory'].method = SSL.SSLv3_METHOD
        senderFactory = ESMTPSenderFactory(self.username, self.password,
                                           self.fromaddr, self.toaddrs, msg,
                                           dfd, **kw)
        reactor.connectTCP(self.mailhost, port, senderFactory)
        return dfd


class ScreenshotColoredSMTPHandler(ColoredSMTPHandler):
    """Email context around a failed email scrape.

    Initialize with selenium webdriver or runtime `patch_webdriver`.
    Takes a screenshot of the current page where an exception was raised.
    Also saves the url and page source, for debugging purposes.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.webdriver = kwargs.pop('webdriver', None)
        super().__init__(*args, **kwargs)

    def _build_html_msg(self, record: logging.LogRecord) -> MIMEMultipart:
        """Build MIME multipart message from record.
        """
        msg = MIMEMultipart()
        msg['Subject'] = self.getSubject(record)
        msg['From'] = self.fromaddr
        msg['To'] = ','.join(self.toaddrs)
        msg['Date'] = formatdate()
        return msg

    def emit(self, record: logging.LogRecord) -> None:
        if self.webdriver is None:
            return super().emit(record)
        name = 'screenshot.png'
        src_name = 'page_source.txt'
        try:
            msg = self._build_html_msg(record)
            text, html = self._format_record(record)
            url = self.webdriver.current_url
            lk = f'<div><a href="{url}">{url}</a></div>'
            html = f'<html><head></head><body>{html}{lk}<img src="cid:{name}"/></body></html>'
            msg.attach(MIMEText(text, 'text'))
            msg.attach(MIMEText(html, 'html'))
            img = MIMEBase('image', 'png')
            img.set_payload(base64.b64decode(self.webdriver.get_screenshot_as_base64()))
            encoders.encode_base64(img)
            img.add_header('Content-ID', name)
            img.add_header('Content-Disposition', 'attachment', filename=name)
            msg.attach(img)
            src = MIMEBase('application', 'octet-stream')
            src.set_payload(self.webdriver.page_source)
            try:
                encoders.encode_base64(src)
            except UnicodeEncodeError:
                page_source_utf = self.webdriver.page_source.encode('utf-8')
                src.set_payload(page_source_utf)
                encoders.encode_base64(src)
            src.add_header('Content-ID', src_name)
            src.add_header('Content-Disposition', 'attachment', filename=src_name)
            msg.attach(src)
            self._send_html_msg(msg.as_string())
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class BufferedColoredSMTPHandler(ColoredSMTPHandler):
    """Get as much of a job log as possible, useful for distributed jobs.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        capacity = kwargs.pop('capacity', 1024)
        flushLevel = kwargs.pop('flushLevel', logging.ERROR)
        super().__init__(*args, **kwargs)
        self.capacity = capacity
        self.flushLevel = flushLevel
        self.buffer: list[logging.LogRecord] = []

    def shouldFlush(self, record: logging.LogRecord) -> bool:
        """Check if buffer should be flushed.
        """
        return len(self.buffer) >= self.capacity

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.buffer.append(record)
            if self.shouldFlush(record):
                self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        """Flush buffered records.
        """
        if not self.buffer:
            return
        try:
            msg = self._build_html_msg(self.buffer[-1])
            formatted = [self._format_record(_) for _ in self.buffer]
            text, html = list(zip(*formatted))
            text = '\n'.join(text)
            html = '<html><head></head><body>{}</body></html>'.format('\n'.join(html))
            msg.attach(MIMEText(text, 'text'))
            msg.attach(MIMEText(html, 'html'))
            self._send_html_msg(msg.as_string())
            self.buffer = []
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            for record in self.buffer:
                self.handleError(record)
            self.buffer = []

    def close(self) -> None:
        """Final flush before closing the handler.
        """
        self.flush()
        super().close()


class ColoredMandrillHandler(ColoredHandler, logging.Handler):
    """Send logging emails via Mandrill HTTP API instead of SMTP.
    """

    def __init__(self, apikey: str, fromaddr: str, toaddrs: str | list[str],
                 subject: str) -> None:
        logging.Handler.__init__(self)
        self.api = None
        if 'MailchimpTransactional' in globals():
            self.api = MailchimpTransactional.Client(apikey)
        self.fromaddr = fromaddr
        if isinstance(toaddrs, str):
            toaddrs = [toaddrs]
        self.toaddrs = [{'email': email} for email in toaddrs]
        self.subject = subject

    def emit(self, record: logging.LogRecord) -> None:
        if self.api is None:
            return
        text, html = self._format_record(record)
        msg = {
            'from_email': self.fromaddr,
            'to': self.toaddrs,
            'subject': self.getSubject(record),
            'html': html,
            'text': text,
            }
        try:
            self.api.messages.send({'message': msg})
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class ScreenshotColoredMandrillHandler(ColoredMandrillHandler):
    """Mandrill version of ScreenshotColoredSMTPHandler.
    """

    def __init__(self, apikey: str, fromaddr: str, toaddrs: str | list[str],
                 subject: str, **kw: Any) -> None:
        self.webdriver = kw.pop('webdriver', None)
        super().__init__(apikey, fromaddr, toaddrs, subject, **kw)

    def emit(self, record: logging.LogRecord) -> None:
        if self.webdriver is None or self.api is None:
            return super().emit(record)
        name = 'screenshot.png'
        src_name = 'page_source.txt'
        try:
            text, html = self._format_record(record)
            url = self.webdriver.current_url
            lk = f'<div><a href="{url}">{url}</a></div>'
            html = f'<html><head></head><body>{html}{lk}<img src="cid:{name}"/></body></html>'
            img = {
                'content': self.webdriver.get_screenshot_as_base64(),
                'name': name,
                'type': 'image/png',
                }
            page_source_b64 = base64.b64encode(
                self.webdriver.page_source.encode('utf-8')).decode('ascii')
            src = {
                'content': page_source_b64,
                'name': src_name,
                'type': 'text/plain',
                }
            msg = {
                'from_email': self.fromaddr,
                'to': self.toaddrs,
                'subject': self.getSubject(record),
                'html': html,
                'text': text,
                'images': [img],
                'attachments': [src],
                }
            self.api.messages.send({'message': msg})
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class URLHandler(HTTPHandler):
    """HTTPHandler with HTTPS and SumoLogic headers.
    """

    def __init__(self, host: str, url: str, method: str = 'POST') -> None:
        super().__init__(host, url, method=method)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            data = self.format(record).encode('utf-8')
            with closing(urllib.request.urlopen(self.host+self.url, data)) as req:
                _ = req.read()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class SNSHandler(ColoredHandler, logging.Handler):
    """AWS SNS Handler using boto3.
    """

    def __init__(self, topic_arn: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.sns_client = None
        self.topic_arn = topic_arn
        if 'boto3' in globals():
            try:
                region_name = topic_arn.split(':')[3]
                self.sns_client = boto3.client('sns', region_name=region_name)
            except Exception:
                pass

    def emit(self, record: logging.LogRecord) -> None:
        if self.sns_client is None:
            return
        try:
            subject = f'{record.name}:{record.levelname}'
            self.sns_client.publish(
                TopicArn=self.topic_arn,
                Message=self.format(record),
                Subject=subject[:99])
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


def _add_default_handler(logger: logging.Logger) -> None:
    """Add default stream handler to logger.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    logger.addHandler(handler)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
