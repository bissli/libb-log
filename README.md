# Logging Library

A flexible and extensible logging system with support for multiple output formats, colorization, and various handlers (console, file, syslog, email, etc.).

## Features

- Multiple preconfigured logging setups (command-line, job, web, twisted, etc.)
- Colorized console output (cross-platform)
- File logging with automatic rotation
- Syslog integration (regular and TLS)
- Email notifications (via SMTP or Mandrill API)
- Screenshot capture for web applications
- AWS SNS integration
- Customizable filters and formatters

## Installation

```bash
# Clone the repository
git clone <repository-url>

# Install the package
pip install -e .
```

## Quick Start

Basic setup for a command-line application:

```python
import logging
from log import configure_logging
import os

# Set environment variable to include your module
os.environ['CONFIG_LOG_MODULES_EXTRA'] = 'myapp,myapp.submodule'
# Or set in your shell before running the application

# Set up logging for a command-line application
configure_logging(setup='cmd')

# Get a module-specific logger (recommended approach)
logger = logging.getLogger(__name__)

# Use standard logging methods
logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')
logger.critical('Critical message')

# Log exceptions with traceback
try:
    1 / 0
except Exception as exc:
    logger.exception(exc)
```

### Module-Specific Logging

This library is designed to work with Python's standard module-specific loggers using `__name__`. To ensure your module loggers receive the proper configuration:

1. Add your module names to the `CONFIG_LOG_MODULES_EXTRA` environment variable
2. Use `logger = logging.getLogger(__name__)` in your modules
3. All configured modules will receive the same handlers and settings as the main logger type

This approach allows you to follow standard Python logging practices while benefiting from the library's handlers and formatting.

## Logging Configurations

The library provides several predefined logging configurations:

- `cmd`: For command-line applications
- `job`: For background job processing
- `twd`: For Twisted applications
- `web`: For web applications
- `srp`: For SRP applications

Example for web applications:

```python
import os
from log import configure_logging
import logging

# Configure your modules to use the library's handlers
os.environ['CONFIG_LOG_MODULES_EXTRA'] = 'myapp.views,myapp.models'

configure_logging(setup='web')
logger = logging.getLogger(__name__)  # Module-specific logger
```

## Logging with Web Frameworks

### Flask

```python
import os
from flask import Flask, request, session
from log import configure_logging
from log.filters import WebServerFilter
import logging

# Add your modules to receive the same configuration as 'web' loggers
os.environ['CONFIG_LOG_MODULES_EXTRA'] = 'myapp.views,myapp.models'

app = Flask(__name__)
configure_logging(setup='web')

# Use module-specific logger
logger = logging.getLogger(__name__)

# Add a web server filter to include IP and user info
# Get the parent logger to add filters to all handlers
web_logger = logging.getLogger('web')
for handler in web_logger.handlers:
    handler.addFilter(WebServerFilter(
        ip_fn=lambda: request.remote_addr,
        user_fn=lambda: session.get('user')
    ))

@app.route('/')
def index():
    logger.info('Request received for index page')
    return 'Hello World'
```

### Capturing Screenshots (Selenium)

```python
import os
from selenium import webdriver
from log import configure_logging, patch_webdriver
import logging

# Configure your modules
os.environ['CONFIG_LOG_MODULES_EXTRA'] = 'myapp.selenium,myapp.tests'

configure_logging(setup='job')
# Use module-specific logger
logger = logging.getLogger(__name__)

# For screenshot functionality, we need to patch the job logger
# as that's where the handlers are configured
job_logger = logging.getLogger('job')
driver = webdriver.Chrome()
# Patch the logger to capture screenshots on errors
patch_webdriver(job_logger, driver)

try:
    driver.get('https://example.com')
    # Error will trigger screenshot capture and email
    assert 'Expected Text' in driver.page_source
except Exception as e:
    logger.exception(e)
finally:
    driver.quit()
```

## Environment Variables Reference

### Core Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONFIG_CHECKTTY` | No | - | When present, enables TTY detection for console output |
| `CONFIG_TMPDIR_DIR` | No | System temp dir | Directory for log files |
| `CONFIG_LOG_MODULES_EXTRA` | No | - | Comma-separated list of additional modules to configure with the same logging settings (e.g., `myapp,myapp.models`) |
| `CONFIG_LOG_MODULES_IGNORE` | No | - | Comma-separated list of modules to ignore in logging |

### Syslog Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONFIG_SYSLOG_HOST` | No | - | Syslog server hostname/IP |
| `CONFIG_SYSLOG_PORT` | No | - | Syslog server port |

### TLS Syslog Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONFIG_TLSSYSLOG_HOST` | No | - | TLS Syslog server hostname/IP |
| `CONFIG_TLSSYSLOG_PORT` | No | - | TLS Syslog server port |
| `CONFIG_TLSSYSLOG_DIR` | No | - | Directory containing TLS certificates for syslog |

### Email Notification Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONFIG_MANDRILL_APIKEY` | No | - | Mandrill API key for sending email notifications |

### AWS Integration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONFIG_SNSLOG_TOPIC_ARN` | No | - | AWS SNS Topic ARN for logging notifications |

## Asyncio Support

This library provides asyncio-safe versions of email notification handlers to prevent blocking the event loop:

```python
import asyncio
import logging
from log import configure_logging
from log.async_handlers import AsyncSafeColoredSMTPHandler

# Configure logging first
configure_logging(setup='cmd')

# Get a logger
logger = logging.getLogger(__name__)

# Replace standard handlers with asyncio-safe versions
for handler in logger.handlers:
    if isinstance(handler, logging.handlers.SMTPHandler):
        logger.removeHandler(handler)
        # Create asyncio-safe handler with same parameters
        async_handler = AsyncSafeColoredSMTPHandler(
            mailhost=handler.mailhost,
            fromaddr=handler.fromaddr,
            toaddrs=handler.toaddrs,
            subject=handler.subject
        )
        logger.addHandler(async_handler)

# Now you can use the logger in asyncio code without blocking
async def main():
    try:
        # Your asyncio code here
        result = await some_async_operation()
    except Exception as e:
        # This won't block the event loop
        logger.exception(e)

# Run the asyncio event loop
asyncio.run(main())
```

## Advanced Usage

### Class-based Logging

```python
import os
from log import class_logger, configure_logging

# Make sure to configure your modules first
os.environ['CONFIG_LOG_MODULES_EXTRA'] = 'myapp,myapp.models'
configure_logging(setup='cmd')  # or your preferred setup

@class_logger
class MyClass:
    def __init__(self):
        self.logger.info("Initialized MyClass instance")

    def do_something(self):
        self.logger.debug("Doing something")
        # ...
```

### Exception Logging Decorator

```python
import os
from log import log_exception, configure_logging
import logging

# Configure your modules
os.environ['CONFIG_LOG_MODULES_EXTRA'] = 'myapp,myapp.utils'
configure_logging(setup='cmd')

# Use module-specific logger
logger = logging.getLogger(__name__)

@log_exception(logger)
def risky_function():
    # This function will log any exceptions that occur
    # while still allowing them to propagate up
    return 1 / 0
```

## Handlers

The library includes several custom log handlers:

- `ColoredStreamHandler`: Colorizes output to terminals
- `NonBufferedFileHandler`: Writes to file without buffering
- `ColoredSMTPHandler`: Sends HTML-formatted colored emails
- `ScreenshotColoredSMTPHandler`: Includes screenshots in error emails
- `ColoredMandrillHandler`: Sends emails via Mandrill API
- `ScreenshotColoredMandrillHandler`: Includes screenshots in Mandrill emails
- `URLHandler`: Posts log messages to an HTTP endpoint
- `SNSHandler`: Sends log messages to AWS SNS

## Filters

Custom filters to enhance log messages:

- `MachineFilter`: Adds hostname to log records
- `PreambleFilter`: Adds preamble information about the application
- `WebServerFilter`: Adds web request context (IP, user) to log records
