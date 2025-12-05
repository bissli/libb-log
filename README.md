# Logging Library

A flexible logging library powered by loguru internally. Provides multiple output formats, colorization, and various sinks (console, file, syslog, email, AWS SNS). Uses standard `logging` module syntax.

## Features

- Standard `logging.getLogger()` and `logger.info()` syntax
- Multiple preconfigured setups (cmd, job, web, twd, srp)
- Colorized console output (DEBUG=purple, INFO=green, WARNING=yellow, ERROR/CRITICAL=red)
- File logging with automatic rotation
- Syslog integration (regular and TLS)
- Email notifications (via SMTP or Mandrill API)
- Screenshot capture for web applications
- AWS SNS integration

## Installation

```bash
pip install -e .
```

## Quick Start

```python
import logging
import log

# Configure logging for your setup type
log.configure_logging('cmd')

# Use standard logging
logger = logging.getLogger('cmd')
logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')

# Child loggers work too
child = logging.getLogger('cmd.mymodule')
child.info('Hello from mymodule')
```

## Setup Types

| Setup | Description | Default Sinks |
|-------|-------------|---------------|
| `cmd` | Command-line applications | Console (DEBUG level) |
| `job` | Background job processing | File, Mail, Syslog, SNS |
| `web` | Web applications | File, Mail, Syslog, SNS |
| `twd` | Twisted applications | Syslog, SNS |
| `srp` | SRP applications | Mail, Syslog, SNS |

## Configuration

```python
import logging
import log

# Basic configuration
log.configure_logging('web', app='myapp')

# With level override
log.configure_logging('job', level='DEBUG')

# With web context for request tracking (framework-agnostic)
log.configure_logging('web', web_context={
    'ip_fn': lambda: request.remote_addr,
    'user_fn': lambda: session.get('user', ''),
})

# With extra handlers
log.configure_logging('job', extra_handlers={
    'cloudwatch': {
        'class': 'watchtower.CloudWatchLogHandler',
        'log_group': 'myapp',
        'level': 'INFO',
    }
})

logger = logging.getLogger('web')
logger.info('Logging configured')
```

## Logging

```python
import logging
import log

log.configure_logging('cmd')
logger = logging.getLogger('cmd')

logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')
logger.critical('Critical message')

# Log exceptions with traceback
try:
    1 / 0
except Exception:
    logger.exception('Something went wrong')
```

## Utilities

```python
import logging
import log

log.configure_logging('cmd')

# Set logging level
log.set_level('DEBUG')

# Flush all sinks on shutdown
log.complete()

# Class decorator for adding logger attribute
@log.class_logger
class MyService:
    def process(self):
        self.logger.info('Processing...')

# Exception logging decorator
logger = logging.getLogger('cmd')

@log.log_exception(logger)
def risky_operation():
    return 1 / 0  # Logs exception and re-raises

# Stderr stream logger (captures print statements)
import sys
wwwlog = logging.getLogger('web.stdout')
sys.stderr = log.StderrStreamLogger(wwwlog)
```

## Web Framework Integration

### web.py

```python
import logging
import web

import log
from tc import config

web_context = {
    'ip_fn': lambda: web.ctx.get('ip', ''),
    'user_fn': lambda: web.ctx.session.get('user', '') if hasattr(web.ctx, 'session') else '',
}

log.configure_logging('web', web_context=web_context)

logger = logging.getLogger('web')
logger.info('Application started')
```

### Flask

```python
import logging
from flask import Flask, request, session

import log

app = Flask(__name__)

log.configure_logging('web', web_context={
    'ip_fn': lambda: request.remote_addr,
    'user_fn': lambda: session.get('user', ''),
})

logger = logging.getLogger('web')

@app.route('/')
def index():
    logger.info('Request received')
    return 'Hello World'
```

### Selenium Screenshots

```python
import logging
from selenium import webdriver

import log

log.configure_logging('job')
logger = logging.getLogger('job')

driver = webdriver.Chrome()
log.patch_webdriver(logger, driver)  # Captures screenshots on errors

try:
    driver.get('https://example.com')
    logger.error('This error will include a screenshot')
finally:
    driver.quit()
```

## Environment Variables

### Core Configuration

| Variable | Description |
|----------|-------------|
| `CONFIG_TMPDIR_DIR` | Directory for log files (default: system temp) |
| `CONFIG_LOG_MODULES_EXTRA` | Comma-separated modules to intercept |

### Syslog

| Variable | Description |
|----------|-------------|
| `CONFIG_SYSLOG_HOST` | Syslog server hostname |
| `CONFIG_SYSLOG_PORT` | Syslog server port |

### TLS Syslog

| Variable | Description |
|----------|-------------|
| `CONFIG_TLSSYSLOG_HOST` | TLS Syslog server hostname |
| `CONFIG_TLSSYSLOG_PORT` | TLS Syslog server port |
| `CONFIG_TLSSYSLOG_DIR` | Directory containing TLS certificates |

### Email Notifications

| Variable | Description |
|----------|-------------|
| `CONFIG_MANDRILL_APIKEY` | Mandrill API key for email notifications |

### AWS Integration

| Variable | Description |
|----------|-------------|
| `CONFIG_SNSLOG_TOPIC_ARN` | AWS SNS Topic ARN for notifications |

## Sinks

The library includes several sink classes for different output destinations:

- `MandrillSink` / `ScreenshotMandrillSink` - Email via Mandrill API
- `SMTPSink` / `ScreenshotSMTPSink` - Email via SMTP
- `SyslogSink` / `TLSSyslogSink` - Syslog output
- `SNSSink` - AWS SNS notifications
- `URLSink` - HTTP POST to log aggregators
