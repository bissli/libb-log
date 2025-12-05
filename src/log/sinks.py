"""Loguru sinks - callable classes that receive log messages.

Each sink is a callable that receives a loguru Message object.
These replace the old logging.Handler subclasses with simpler callables.
"""
from __future__ import annotations

import base64
import logging
import smtplib
import urllib.request
from contextlib import closing
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from logging.handlers import SysLogHandler
from typing import TYPE_CHECKING

from loguru import logger as _loguru

if TYPE_CHECKING:
    from loguru import Message

# Optional dependency flags
HAS_BOTO3 = False
HAS_MAILCHIMP = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    pass

try:
    import mailchimp_transactional as MailchimpTransactional
    HAS_MAILCHIMP = True
except ImportError:
    pass

__all__ = [
    'MandrillSink',
    'ScreenshotMandrillSink',
    'SMTPSink',
    'ScreenshotSMTPSink',
    'SNSSink',
    'SyslogSink',
    'TLSSyslogSink',
    'URLSink',
]


def _choose_color_html(level_name: str) -> str:
    """Choose HTML color based on log level name."""
    level_colors = {
        'CRITICAL': '#EE0000',
        'ERROR': '#EE0000',
        'WARNING': '#DAA520',
        'INFO': '#228B22',
        'DEBUG': '#D0D2C4',
    }
    return level_colors.get(level_name, '#000')


class MandrillSink:
    """Email sink via Mandrill API.

    Sends log messages as HTML emails via the Mandrill/Mailchimp API.
    """

    def __init__(
        self,
        apikey: str,
        fromaddr: str,
        toaddrs: str | list[str],
        subject_template: str = '{extra[machine]} {name} {level.name}',
    ):
        self.api = None
        if HAS_MAILCHIMP:
            self.api = MailchimpTransactional.Client(apikey)
        self.fromaddr = fromaddr
        if isinstance(toaddrs, str):
            toaddrs = [toaddrs]
        self.toaddrs = [{'email': email} for email in toaddrs]
        self.subject_template = subject_template

    def __call__(self, message: Message) -> None:
        if self.api is None:
            return
        record = message.record
        text = str(message)
        color = _choose_color_html(record['level'].name)
        html = f'<pre style="color:{color};">{text}</pre>'

        # Format subject from template
        subject = self.subject_template.format(**record)

        msg = {
            'from_email': self.fromaddr,
            'to': self.toaddrs,
            'subject': subject,
            'html': html,
            'text': text,
        }
        try:
            self.api.messages.send({'message': msg})
        except Exception as e:
            _loguru.opt(depth=1).warning(f'MandrillSink failed: {e}')


class ScreenshotMandrillSink(MandrillSink):
    """Mandrill email sink with webdriver screenshot attachment.

    Use set_webdriver() to patch in a selenium webdriver at runtime.
    """

    def __init__(self, *args, webdriver=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.webdriver = webdriver

    def set_webdriver(self, webdriver) -> None:
        """Runtime webdriver patching."""
        self.webdriver = webdriver

    def __call__(self, message: Message) -> None:
        if self.webdriver is None or self.api is None:
            return super().__call__(message)

        record = message.record
        text = str(message)
        color = _choose_color_html(record['level'].name)

        try:
            url = self.webdriver.current_url
            link = f'<div><a href="{url}">{url}</a></div>'
            html = f'<html><body><pre style="color:{color};">{text}</pre>{link}<img src="cid:screenshot.png"/></body></html>'

            img = {
                'content': self.webdriver.get_screenshot_as_base64(),
                'name': 'screenshot.png',
                'type': 'image/png',
            }
            page_source_b64 = base64.b64encode(
                self.webdriver.page_source.encode('utf-8')
            ).decode('ascii')
            src = {
                'content': page_source_b64,
                'name': 'page_source.txt',
                'type': 'text/plain',
            }

            subject = self.subject_template.format(**record)
            msg = {
                'from_email': self.fromaddr,
                'to': self.toaddrs,
                'subject': subject,
                'html': html,
                'text': text,
                'images': [img],
                'attachments': [src],
            }
            self.api.messages.send({'message': msg})
        except Exception as e:
            _loguru.opt(depth=1).warning(f'ScreenshotMandrillSink failed: {e}')
            super().__call__(message)


class SMTPSink:
    """Email sink via SMTP."""

    def __init__(
        self,
        mailhost: str,
        port: int,
        fromaddr: str,
        toaddrs: str | list[str],
        subject_template: str = '{extra[machine]} {name} {level.name}',
        username: str | None = None,
        password: str | None = None,
        ssl: bool = False,
        starttls: bool = False,
    ):
        self.mailhost = mailhost
        self.port = port or smtplib.SMTP_PORT
        self.fromaddr = fromaddr
        self.toaddrs = [toaddrs] if isinstance(toaddrs, str) else toaddrs
        self.subject_template = subject_template
        self.username = username
        self.password = password
        self.ssl = ssl
        self.starttls = starttls

    def __call__(self, message: Message) -> None:
        record = message.record
        text = str(message)
        color = _choose_color_html(record['level'].name)
        html = f'<html><body><pre style="color:{color};">{text}</pre></body></html>'

        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.subject_template.format(**record)
        msg['From'] = self.fromaddr
        msg['To'] = ','.join(self.toaddrs)
        msg['Date'] = formatdate()
        msg.attach(MIMEText(text, 'text'))
        msg.attach(MIMEText(html, 'html'))

        try:
            if self.ssl:
                smtp = smtplib.SMTP_SSL(self.mailhost, self.port)
            else:
                smtp = smtplib.SMTP(self.mailhost, self.port)
            if self.starttls:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, msg.as_string())
            smtp.quit()
        except Exception as e:
            _loguru.opt(depth=1).warning(f'SMTPSink failed: {e}')


class ScreenshotSMTPSink(SMTPSink):
    """SMTP email sink with webdriver screenshot attachment."""

    def __init__(self, *args, webdriver=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.webdriver = webdriver

    def set_webdriver(self, webdriver) -> None:
        """Runtime webdriver patching."""
        self.webdriver = webdriver

    def __call__(self, message: Message) -> None:
        if self.webdriver is None:
            return super().__call__(message)

        record = message.record
        text = str(message)
        color = _choose_color_html(record['level'].name)

        try:
            url = self.webdriver.current_url
            link = f'<div><a href="{url}">{url}</a></div>'
            html = f'<html><body><pre style="color:{color};">{text}</pre>{link}<img src="cid:screenshot.png"/></body></html>'

            msg = MIMEMultipart()
            msg['Subject'] = self.subject_template.format(**record)
            msg['From'] = self.fromaddr
            msg['To'] = ','.join(self.toaddrs)
            msg['Date'] = formatdate()
            msg.attach(MIMEText(text, 'text'))
            msg.attach(MIMEText(html, 'html'))

            # Screenshot attachment
            img = MIMEBase('image', 'png')
            img.set_payload(base64.b64decode(self.webdriver.get_screenshot_as_base64()))
            encoders.encode_base64(img)
            img.add_header('Content-ID', 'screenshot.png')
            img.add_header('Content-Disposition', 'attachment', filename='screenshot.png')
            msg.attach(img)

            # Page source attachment
            src = MIMEBase('application', 'octet-stream')
            src.set_payload(self.webdriver.page_source.encode('utf-8'))
            encoders.encode_base64(src)
            src.add_header('Content-ID', 'page_source.txt')
            src.add_header('Content-Disposition', 'attachment', filename='page_source.txt')
            msg.attach(src)

            if self.ssl:
                smtp = smtplib.SMTP_SSL(self.mailhost, self.port)
            else:
                smtp = smtplib.SMTP(self.mailhost, self.port)
            if self.starttls:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, msg.as_string())
            smtp.quit()
        except Exception as e:
            _loguru.opt(depth=1).warning(f'ScreenshotSMTPSink failed: {e}')
            super().__call__(message)


class SNSSink:
    """AWS SNS notification sink."""

    def __init__(self, topic_arn: str):
        self.topic_arn = topic_arn
        self.client = None
        if HAS_BOTO3:
            try:
                region = topic_arn.split(':')[3]
                self.client = boto3.client('sns', region_name=region)
            except Exception as e:
                _loguru.opt(depth=1).warning(f'SNSSink init failed: {e}')

    def __call__(self, message: Message) -> None:
        if self.client is None:
            return
        record = message.record
        try:
            subject = f"{record.get('name', '')}:{record['level'].name}"[:99]
            self.client.publish(
                TopicArn=self.topic_arn,
                Message=str(message),
                Subject=subject,
            )
        except Exception as e:
            _loguru.opt(depth=1).warning(f'SNSSink failed: {e}')


class SyslogSink:
    """Syslog sink using stdlib SysLogHandler."""

    def __init__(self, host: str, port: int = 514):
        self.handler = SysLogHandler(address=(host, port))

    def __call__(self, message: Message) -> None:
        record = message.record
        level = getattr(logging, record['level'].name, logging.INFO)
        log_record = logging.LogRecord(
            name=record.get('name', ''),
            level=level,
            pathname='',
            lineno=record.get('line', 0),
            msg=str(message),
            args=(),
            exc_info=None,
        )
        try:
            self.handler.emit(log_record)
        except Exception as e:
            _loguru.opt(depth=1).warning(f'SyslogSink failed: {e}')


class TLSSyslogSink:
    """TLS Syslog sink."""

    def __init__(self, host: str, port: int, certs_dir: str | None = None):
        self.handler = None
        try:
            from tls_syslog import TLSSysLogHandler
            self.handler = TLSSysLogHandler(
                address=(host, port),
                certs_dir=certs_dir,
            )
        except ImportError:
            pass

    def __call__(self, message: Message) -> None:
        if self.handler is None:
            return
        record = message.record
        level = getattr(logging, record['level'].name, logging.INFO)
        log_record = logging.LogRecord(
            name=record.get('name', ''),
            level=level,
            pathname='',
            lineno=record.get('line', 0),
            msg=str(message),
            args=(),
            exc_info=None,
        )
        try:
            self.handler.emit(log_record)
        except Exception as e:
            _loguru.opt(depth=1).warning(f'TLSSyslogSink failed: {e}')


class URLSink:
    """HTTP POST sink for log aggregators."""

    def __init__(self, url: str):
        self.url = url

    def __call__(self, message: Message) -> None:
        try:
            data = str(message).encode('utf-8')
            with closing(urllib.request.urlopen(self.url, data)) as req:
                _ = req.read()
        except Exception as e:
            _loguru.opt(depth=1).warning(f'URLSink failed: {e}')
