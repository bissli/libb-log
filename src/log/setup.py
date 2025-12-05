"""Logging configuration - declarative loguru-based implementation.
"""
from __future__ import annotations

import datetime
import importlib
import logging
import os
import socket
import sys
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from functools import wraps
from typing import Any

from libb import is_tty, scriptname
from log import config as config_log
from log._backend import get_backend, intercept_stdlib

try:
    from mail import config as config_mail
    MAIL_CONFIG_AVAILABLE = True
except ImportError:
    MAIL_CONFIG_AVAILABLE = False

try:
    import mailchimp_transactional as MailchimpTransactional
    MAILCHIMP_ENABLED = True
except ImportError:
    MAILCHIMP_ENABLED = False

if sys.platform == 'win32':
    try:
        import colorama
        colorama.just_fix_windows_console()
    except ImportError:
        pass

# Keys to skip when parsing extra_handlers config
_HANDLER_SKIP_KEYS = {'()', 'class', 'level', 'formatter', 'filters'}

# DNS lookup timeout for web patcher (seconds)
_DNS_TIMEOUT = 1.0


__all__ = [
    'configure_logging',
    'log_exception',
    'patch_webdriver',
    'class_logger',
    'set_level',
    'SetupType',
]


class SetupType(StrEnum):
    """Setup types for logging configuration."""
    CMD = 'cmd'
    JOB = 'job'
    WEB = 'web'
    TWD = 'twd'
    SRP = 'srp'


# Format strings for loguru
# <level> tags apply the level's color to the entire line
# {extra[logger_name]} shows the stdlib logger name (e.g., 'cmd', 'web')
FMT_JOB = '<level>{level.name:<4} {time:YYYY-MM-DD HH:mm:ss,SSS} {extra[machine]} {extra[logger_name]} {line} {message}</level>'
FMT_WEB = '<level>{level.name:<4} {time:YYYY-MM-DD HH:mm:ss,SSS} {extra[machine]} {extra[logger_name]} {line} [{extra[user]} {extra[ip]}] {message}</level>'


@dataclass
class LogConfig:
    """Declarative logging configuration."""
    setup: SetupType
    app: str = ''
    app_args: str = ''
    level: str = 'INFO'

    # Sinks to enable
    console: bool = True
    file: bool = False
    mail: bool = False
    syslog: bool = False
    tlssyslog: bool = False
    sns: bool = False

    # Context
    web_context: dict = field(default_factory=dict)


# Preset configurations per setup type
PRESETS: dict[SetupType, LogConfig] = {
    SetupType.CMD: LogConfig(SetupType.CMD, level='DEBUG', console=True),
    SetupType.JOB: LogConfig(SetupType.JOB, file=True, mail=True, syslog=True, tlssyslog=True, sns=True),
    SetupType.WEB: LogConfig(SetupType.WEB, file=True, mail=True, syslog=True, tlssyslog=True, sns=True),
    SetupType.TWD: LogConfig(SetupType.TWD, syslog=True, tlssyslog=True, sns=True),
    SetupType.SRP: LogConfig(SetupType.SRP, mail=True, syslog=True, tlssyslog=True, sns=True),
}


# Track screenshot sinks for webdriver patching
_screenshot_sinks: list = []


def configure_logging(
    setup: SetupType | str | None = None,
    app: str | None = None,
    app_args: list[str] | None = None,
    level: str | None = None,
    extra_handlers: dict[str, dict[str, Any]] | None = None,
    web_context: dict[str, Callable[[], str]] | None = None,
) -> None:
    """Configure logging for any application.

    Args:
        setup: Setup type ('cmd', 'job', 'web', 'twd', 'srp') or SetupType enum
        app: Application name (defaults to script name)
        app_args: Application arguments
        level: Logging level override
        extra_handlers: Dict of handler_name -> handler_config for custom handlers
        web_context: Dict with 'ip_fn' and 'user_fn' callables for web request context.
                     Example for Flask:
                         web_context={
                             'ip_fn': lambda: flask.request.remote_addr,
                             'user_fn': lambda: flask.session.get('user', ''),
                         }
    """
    global _screenshot_sinks
    _screenshot_sinks.clear()

    backend = get_backend()
    backend.reset()

    # Normalize inputs
    if isinstance(setup, str):
        setup = SetupType(setup)
    setup_type = setup or SetupType.CMD

    if app_args is None:
        app_args = []
    if not app:
        app = scriptname()
        app_args = sys.argv[1:]

    # Get preset and create a copy to modify
    config = deepcopy(PRESETS[setup_type])
    config.app = app
    config.app_args = ' '.join(app_args)

    if level:
        config.level = level.upper()
    if web_context:
        config.web_context = web_context

    # Configure context patchers
    _configure_context(backend, config)

    # Add sinks based on config
    _add_sinks(backend, config)

    # Handle extra_handlers (backward compatibility)
    if extra_handlers:
        _add_extra_handlers(backend, config, extra_handlers)

    # Set up stdlib logging interception
    # This makes logging.getLogger('web').info(...) work
    intercept_stdlib(['cmd', 'job', 'web', 'twd', 'srp'])

    # Also intercept extra modules from config
    extra_modules = (config_log.log.modules.extra or '').split(',')
    extra_modules = [m.strip() for m in extra_modules if m.strip()]
    if extra_modules:
        intercept_stdlib(extra_modules)


def _configure_context(backend, config: LogConfig) -> None:
    """Set up context patchers (machine, preamble, web)."""
    patchers = []

    # Machine patcher - always add hostname
    hostname = socket.gethostname()

    def machine_patcher(record):
        record['extra']['machine'] = hostname
    patchers.append(machine_patcher)

    # Preamble patcher - for job/srp/twd setups
    if config.setup in {SetupType.JOB, SetupType.SRP, SetupType.TWD}:
        preamble_state = {'status': 'succeeded'}

        def preamble_patcher(record):
            record['extra']['cmd_app'] = config.app
            record['extra']['cmd_args'] = config.app_args
            record['extra']['cmd_setup'] = config.setup.value
            # Track failure status
            if record['level'].no >= logging.ERROR:
                preamble_state['status'] = 'failed'
            record['extra']['cmd_status'] = preamble_state['status']

        patchers.append(preamble_patcher)

    # Web patcher - for web setup or when web_context provided
    if config.setup == SetupType.WEB or config.web_context:
        ip_fn = config.web_context.get('ip_fn', lambda: '')
        user_fn = config.web_context.get('user_fn', lambda: '')

        def resolve_ip():
            try:
                ipaddr = ip_fn() or ''
                if not ipaddr:
                    return ''
                old_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(_DNS_TIMEOUT)
                try:
                    return socket.gethostbyaddr(ipaddr)[0]
                except (TimeoutError, OSError):
                    return ipaddr
                finally:
                    socket.setdefaulttimeout(old_timeout)
            except Exception:
                return ''

        def web_patcher(record):
            record['extra']['ip'] = resolve_ip()
            record['extra']['user'] = user_fn() or ''

        patchers.append(web_patcher)

    # Combine all patchers
    def combined_patcher(record):
        for patcher in patchers:
            patcher(record)

    backend.configure(patcher=combined_patcher)


def _add_sinks(backend, config: LogConfig) -> None:
    """Add sinks based on configuration."""
    fmt = FMT_WEB if config.setup == SetupType.WEB else FMT_JOB
    diagnose = config_log.log.enable_diagnose

    # When in TTY, use DEBUG level for interactive debugging
    if config.console or config.setup == SetupType.CMD or is_tty():
        console_level = 'DEBUG' if is_tty() else config.level
        backend.add_sink(
            sys.stderr,
            level=console_level,
            format=fmt,
            colorize=None,
            backtrace=False,
            diagnose=diagnose,
        )

    # File sink - if enabled
    if config.file:
        filename = os.path.join(
            config_log.tmpdir.dir,
            f'{config.app}_{datetime.datetime.now():%Y%m%d_%H%M%S}.log'
        )
        rotation = '1 day' if config.setup == SetupType.WEB else None
        retention = '3 days' if config.setup == SetupType.WEB else None
        backend.add_sink(
            filename,
            level='WARNING',
            format=fmt,
            rotation=rotation,
            retention=retention,
            backtrace=False,
            diagnose=diagnose,
        )

    # Mail sink - if enabled and configured
    if config.mail and _mail_configured():
        from log.sinks import ScreenshotMandrillSink
        sink = ScreenshotMandrillSink(
            apikey=config_mail.mandrill.apikey,
            fromaddr=config_mail.mail.fromemail,
            toaddrs=config_mail.mail.toemail,
            subject_template='{extra[machine]} {name} {level.name}',
        )
        _screenshot_sinks.append(sink)
        backend.add_sink(sink, level='ERROR', format=fmt, backtrace=False, diagnose=diagnose)

    # Syslog sink - if enabled and configured
    if config.syslog and _syslog_configured():
        from log.sinks import SyslogSink
        sink = SyslogSink(
            host=config_log.syslog.host,
            port=config_log.syslog.port,
        )
        backend.add_sink(sink, level='INFO', format=fmt, backtrace=False, diagnose=diagnose)

    # TLS Syslog sink - if enabled and configured
    if config.tlssyslog and _tlssyslog_configured():
        from log.sinks import TLSSyslogSink
        sink = TLSSyslogSink(
            host=config_log.tlssyslog.host,
            port=config_log.tlssyslog.port,
            certs_dir=config_log.tlssyslog.dir,
        )
        backend.add_sink(sink, level='INFO', format=fmt, backtrace=False, diagnose=diagnose)

    # SNS sink - if enabled and configured
    if config.sns and _sns_configured():
        from log.sinks import SNSSink
        topic_arn = os.getenv('CONFIG_SNSLOG_TOPIC_ARN')
        sink = SNSSink(topic_arn=topic_arn)
        backend.add_sink(sink, level='ERROR', format=fmt, backtrace=False, diagnose=diagnose)


def _add_extra_handlers(backend, config: LogConfig, extra_handlers: dict) -> None:
    """Add extra handlers (backward compatibility with dictConfig style).

    Supports both:
    - Direct handler instances
    - dictConfig-style dicts with '()' factory syntax
    """
    fmt = FMT_WEB if config.setup == SetupType.WEB else FMT_JOB
    diagnose = config_log.log.enable_diagnose

    for handler_conf in extra_handlers.values():
        if callable(handler_conf) and not isinstance(handler_conf, dict):
            # Already a handler/sink instance
            backend.add_sink(handler_conf, level='INFO', format=fmt, backtrace=False, diagnose=diagnose)
            continue

        if not isinstance(handler_conf, dict):
            continue

        handler_level = handler_conf.get('level', 'INFO')

        # Handle '()' factory syntax (dictConfig style)
        if '()' in handler_conf:
            factory = handler_conf['()']
            # Import the class
            if isinstance(factory, str):
                parts = factory.rsplit('.', 1)
                if len(parts) == 2:
                    module_name, class_name = parts
                    module = importlib.import_module(module_name)
                    factory = getattr(module, class_name)

            # Get constructor args (exclude config keys)
            kwargs = {k: v for k, v in handler_conf.items() if k not in _HANDLER_SKIP_KEYS}
            handler = factory(**kwargs)
            backend.add_sink(handler, level=handler_level, format=fmt, backtrace=False, diagnose=diagnose)

        # Handle 'class' syntax
        elif 'class' in handler_conf:
            class_path = handler_conf['class']
            if isinstance(class_path, str):
                parts = class_path.rsplit('.', 1)
                if len(parts) == 2:
                    module_name, class_name = parts
                    module = importlib.import_module(module_name)
                    handler_class = getattr(module, class_name)

                    kwargs = {k: v for k, v in handler_conf.items() if k not in _HANDLER_SKIP_KEYS}
                    handler = handler_class(**kwargs)
                    backend.add_sink(handler, level=handler_level, format=fmt, backtrace=False, diagnose=diagnose)


def _mail_configured() -> bool:
    """Check if mail handler is configured."""
    return (
        MAIL_CONFIG_AVAILABLE
        and MAILCHIMP_ENABLED
        and bool(os.getenv('CONFIG_MANDRILL_APIKEY'))
    )


def _syslog_configured() -> bool:
    """Check if syslog handler is configured."""
    return bool(
        os.getenv('CONFIG_SYSLOG_HOST')
        and os.getenv('CONFIG_SYSLOG_PORT')
    )


def _tlssyslog_configured() -> bool:
    """Check if TLS syslog handler is configured."""
    return bool(
        os.getenv('CONFIG_TLSSYSLOG_HOST')
        and os.getenv('CONFIG_TLSSYSLOG_PORT')
    )


def _sns_configured() -> bool:
    """Check if SNS handler is configured."""
    return bool(os.getenv('CONFIG_SNSLOG_TOPIC_ARN'))


def set_level(levelname: str) -> None:
    """Set the logging level.

    Note: With loguru, this affects all sinks. For more granular control,
    add sinks with specific levels.
    """
    # For backward compatibility with stdlib code that checks levels
    level_names = {v: k for k, v in logging._levelToName.items()}
    level_names['WARN'] = level_names['WARNING']
    level = level_names.get(levelname.upper(), logging.INFO)
    logging.root.setLevel(level)


def patch_webdriver(this_logger: Any, this_webdriver: Any) -> None:
    """Patch screenshot sinks with webdriver instance.

    Args:
        this_logger: Logger instance (kept for backward compat, ignored)
        this_webdriver: Selenium webdriver instance
    """

    for sink in _screenshot_sinks:
        if hasattr(sink, 'set_webdriver'):
            sink.set_webdriver(this_webdriver)

    # Also check if logger has bound sinks (backward compat)
    if hasattr(this_logger, 'handlers'):
        for h in this_logger.handlers:
            if hasattr(h, 'webdriver'):
                h.webdriver = this_webdriver


_logged_classes: set[type] = set()


def class_logger(cls: type, enable: bool | str = False) -> type:
    """Add logger attribute to a class.

    The logger is a stdlib logger that gets intercepted by loguru.
    """
    logger = logging.getLogger(cls.__module__ + '.' + cls.__name__)
    if enable == 'debug':
        logger.setLevel(logging.DEBUG)
    elif enable == 'info':
        logger.setLevel(logging.INFO)
    cls._should_log_debug = lambda self: logger.isEnabledFor(logging.DEBUG)
    cls._should_log_info = lambda self: logger.isEnabledFor(logging.INFO)
    cls.logger = logger
    _logged_classes.add(cls)
    return cls


def log_exception(logger: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that logs exceptions and re-raises them.

    Works with both stdlib loggers and facade Logger instances.
    """
    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapped_fn(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if hasattr(logger, 'exception'):
                    logger.exception(str(exc))
                raise
        return wrapped_fn
    return wrapper
