# libb-log Architecture Guide

## 1. Architecture Overview

| Module        | Purpose                                                                                |
| ------------- | -------------------------------------------------------------------------------------- |
| `__init__.py` | Public API surface -- re-exports, module-level convenience functions (`log.info(...)`) |
| `_logger.py`  | `Logger` facade class -- abstracts loguru from consumers                               |
| `_backend.py` | Loguru backend singleton, module filter (whitelist), stdlib interception               |
| `setup.py`    | `configure_logging()` entry point, presets, context patchers, sink wiring              |
| `sinks.py`    | Callable sink classes (Mandrill, SMTP, Syslog, SNS, URL, screenshot variants)          |
| `config.py`   | Environment variable parsing into `Setting` objects                                    |
| `loggers.py`  | `StderrStreamLogger` -- redirects stderr to log.info                                   |

Dependency direction: `__init__` -> `_logger`, `setup` -> `_backend`, `sinks`.
`_backend` and `sinks` are leaf modules (no intra-package imports except `config`).

---

## 2. Setup Flow

`configure_logging(setup_type)` is the single entry point. Steps in order:

1. **Clear screenshot sinks** -- `_screenshot_sinks.clear()`
2. **Reset backend** -- `backend.reset()` removes all loguru sinks, reapplies level colors
3. **Normalize inputs** -- coerce `setup` string to `SetupType` enum, default to CMD
4. **Copy preset** -- `deepcopy(PRESETS[setup_type])` so mutations don't leak
5. **Apply overrides** -- `level`, `web_context` from caller args
6. **Configure context patchers** -- `_configure_context()` composes machine + preamble + web patchers
7. **Add sinks** -- `_add_sinks()` reads the `LogConfig` booleans and instantiates enabled sinks
8. **Extra handlers** -- `_add_extra_handlers()` for backward-compat dictConfig-style handlers
9. **Intercept stdlib** -- `intercept_stdlib()` for base loggers (cmd/job/web/twd/srp)
10. **Intercept extra modules** -- parsed from `CONFIG_LOG_MODULES_EXTRA`

If `configure_logging` is never called (e.g., missing from `SvcDoRun`), no sinks
are registered and all log output is silently dropped by loguru.

---

## 3. Presets

| SetupType | console | file | mail | syslog | tlssyslog | sns |
| --------- | ------- | ---- | ---- | ------ | --------- | --- |
| `CMD`     | Yes     | -    | -    | -      | -         | -   |
| `JOB`     | -       | Yes  | Yes  | Yes    | Yes       | Yes |
| `WEB`     | -       | Yes  | Yes  | Yes    | Yes       | Yes |
| `TWD`     | -       | -    | -    | Yes    | Yes       | Yes |
| `SRP`     | -       | -    | Yes  | Yes    | Yes       | Yes |

- CMD sets `level='DEBUG'`; all others default to `'INFO'`.
- JOB and WEB are identical in sinks but differ in format string (FMT_JOB vs FMT_WEB).
- SRP is like JOB minus file sink -- email alerts only, no local file output.
- TTY mode overrides: disables all sinks except console and file (see Section 9).

---

## 4. Sink Pipeline

How a log call flows from user code to output:

```
User code                     Logger._log()
  |                               |
  v                               v
log.info("msg")  --->  _backend.get_backend().log(level, msg, ...)
                                  |
                                  v
                       _loguru.bind(...).opt(...).log(level, msg)
                                  |
                                  v
                       loguru internal processing:
                         1. Run patcher (combined_patcher)
                         2. Create record dict
                         3. For each registered sink:
                            a. Apply filter (_module_filter AND any user filter)
                            b. Format message using format string
                            c. Call sink(message)
```

Sink callables receive a `loguru.Message` object (a `str` subclass with a
`.record` dict attribute). Each sink's `__call__` extracts what it needs from
`message.record` and `str(message)`.

`Backend.add_sink` automatically composes `_module_filter` with any user-supplied
filter via `composed()`. This means every sink gets the whitelist filter.

---

## 5. Context Patchers

Patchers modify the log record dict before sinks see it. They are composed
into a single `combined_patcher` and passed to `_loguru.configure(patcher=...)`.

### Machine patcher (always active)

Sets `record['extra']['machine']` to `socket.gethostname()` and defaults
`record['extra']['logger_name']` to `record['name']`.

### Preamble patcher (JOB, SRP, TWD)

Sets `cmd_app`, `cmd_args`, `cmd_setup`, and tracks `cmd_status` (starts as
`'succeeded'`, flips to `'failed'` on any ERROR+ message). This state is
shared across all log calls in the process via closure.

### Web patcher (WEB, or when `web_context` provided)

Sets `record['extra']['ip']` (with DNS reverse lookup, 1s timeout) and
`record['extra']['user']` from caller-supplied `ip_fn`/`user_fn` callables.

---

## 6. Sinks Reference

### MandrillSink

- **Transport**: Mandrill/Mailchimp Transactional API
- **Config**: `CONFIG_MANDRILL_APIKEY` (env var), `fromaddr`, `toaddrs`
- **Behavior**: Sends HTML email with colored log text
- **Guard**: `@warn_once_if_none('api', ...)` -- warns once if mailchimp lib missing
- **Subject**: Formatted from template, falls back to `{name} {level}` on KeyError

### ScreenshotMandrillSink (extends MandrillSink)

- **Extra**: Attaches webdriver screenshot (base64 PNG) and page source
- **Fallback**: If `webdriver is None` or `api is None`, delegates to `super().__call__`
- **Fallback on error**: Catches exceptions and falls back to `super().__call__`

### SMTPSink

- **Transport**: Direct SMTP (supports SSL, STARTTLS, auth)
- **Config**: `mailhost`, `port`, `fromaddr`, `toaddrs`, `username`, `password`
- **Behavior**: Sends multipart email (text + HTML)
- **Subject**: Same template/fallback pattern as MandrillSink

### ScreenshotSMTPSink (extends SMTPSink)

- **Extra**: Attaches webdriver screenshot and page source as MIME attachments
- **Fallback**: If `webdriver is None`, delegates to `super().__call__`
- **Fallback on error**: Catches exceptions and falls back to `super().__call__`

### SNSSink

- **Transport**: AWS SNS via boto3
- **Config**: `CONFIG_SNSLOG_TOPIC_ARN` (env var)
- **Guard**: `@warn_once_if_none('client', ...)` -- warns once if boto3 missing
- **Subject**: Truncated to 99 chars (SNS limit)

### SyslogSink

- **Transport**: stdlib `SysLogHandler` (UDP)
- **Config**: `CONFIG_SYSLOG_HOST`, `CONFIG_SYSLOG_PORT`
- **Behavior**: Converts loguru record to stdlib `LogRecord`, emits via handler

### TLSSyslogSink

- **Transport**: `tls_syslog.TLSSysLogHandler` (TCP+TLS)
- **Config**: `CONFIG_TLSSYSLOG_HOST`, `CONFIG_TLSSYSLOG_PORT`, `CONFIG_TLSSYSLOG_DIR`
- **Behavior**: Same as SyslogSink but over TLS. Silently no-ops if `tls_syslog` not installed
- **Note**: No `@warn_once_if_none` -- silent return is intentional (init is also silent)

### URLSink

- **Transport**: HTTP POST via `urllib.request.urlopen`
- **Config**: URL string
- **Behavior**: Posts raw log text as request body

### PlaywrightScreenshotAdapter

Not a sink -- adapter that wraps a Playwright browser to provide the Selenium
`webdriver` interface (`current_url`, `get_screenshot_as_base64`, `page_source`).

---

## 7. Module Filter

The module filter (`_backend._module_filter`) is a whitelist that controls which
log messages reach sinks. Applied automatically to every sink via `add_sink()`.

### Rules

1. **ERROR+ always passes** -- `record['level'].no >= 40` bypasses the filter
2. **Check module name** -- `record['name']` against allowed prefixes
3. **Check logger_name** -- `record['extra']['logger_name']` (set by intercepted stdlib logs)

### Allowed modules

- **Base**: `_BASE_MODULES = {'cmd', 'job', 'web', 'twd', 'srp', 'log'}`
- **Extra**: Parsed from `CONFIG_LOG_MODULES_EXTRA` (comma-separated)
- **Cached**: Parsed once, cached in `_allowed_modules` (reset via `_reset_module_cache()`)

### Matching

Prefix-based: module `'web'` matches `'web'` and `'web.routes'` but not `'webapp'`.

---

## 8. stdlib Interception

### Why it's needed

The codebase uses `logging.getLogger('job').info(...)` extensively. Without
interception, these calls go to stdlib handlers and bypass loguru entirely.

### InterceptHandler

A `logging.Handler` subclass that:

1. Maps stdlib level name to loguru level
2. Walks the call stack to find the original caller (skipping `logging` frames)
3. Calls `_loguru.bind(logger_name=record.name).opt(depth=depth).log(level, msg)`

### intercept_stdlib(logger_names)

1. Replaces root logger handlers with `InterceptHandler` via `basicConfig(force=True)`
2. For each named logger: sets handlers to `[InterceptHandler()]`, disables propagation,
   sets level to DEBUG (lets loguru handle filtering)

### Which loggers are intercepted

- Always: `['cmd', 'job', 'web', 'twd', 'srp']`
- Extra: modules from `CONFIG_LOG_MODULES_EXTRA`

---

## 9. TTY Mode

When `is_tty()` returns True (interactive terminal session):

1. **Sink restriction**: All sinks except `console` and `file` are disabled
   (`_TTY_SINKS = {'console', 'file'}`)
2. **Console level**: Forced to `DEBUG` regardless of preset level
3. **Purpose**: During interactive debugging, prevent emails/SNS/syslog noise

Detection: `is_tty()` is imported from `libb` (checks `sys.stdin.isatty()`
and related heuristics).

---

## 10. Environment Variables

| Variable                     | Used in                                         | Purpose                                               |
| ---------------------------- | ----------------------------------------------- | ----------------------------------------------------- |
| `CONFIG_MANDRILL_APIKEY`     | `setup._mail_configured()`                      | Mandrill API key for email sink                       |
| `CONFIG_SYSLOG_HOST`         | `config.py`, `setup._syslog_configured()`       | Syslog server hostname                                |
| `CONFIG_SYSLOG_PORT`         | `config.py`, `setup._syslog_configured()`       | Syslog server port                                    |
| `CONFIG_TLSSYSLOG_HOST`      | `config.py`, `setup._tlssyslog_configured()`    | TLS syslog server hostname                            |
| `CONFIG_TLSSYSLOG_PORT`      | `config.py`, `setup._tlssyslog_configured()`    | TLS syslog server port                                |
| `CONFIG_TLSSYSLOG_DIR`       | `config.py`                                     | Directory containing TLS certificates                 |
| `CONFIG_SNSLOG_TOPIC_ARN`    | `setup._sns_configured()`, `setup._add_sinks()` | AWS SNS topic ARN                                     |
| `CONFIG_LOG_MODULES_EXTRA`   | `config.py`, `_backend._get_allowed_modules()`  | Comma-separated extra module names for whitelist      |
| `CONFIG_LOG_MODULES_IGNORE`  | `config.py`                                     | Comma-separated modules to ignore (parsed but unused) |
| `CONFIG_LOG_ENABLE_DIAGNOSE` | `config.py`                                     | Enable loguru diagnose mode (`1`/`true`/`yes`)        |

Mail sink also requires `libb-mail` config module to be importable (provides
`config_mail.mandrill.apikey`, `config_mail.mail.fromemail`, `config_mail.mail.toemail`).

---

## Helper Functions in sinks.py

### warn_once_if_none(attr_name, warning_msg)

Decorator for `__call__` methods. If `getattr(self, attr_name)` is None, logs a
warning (once per decorated function, shared across instances via closure) and
returns None. Used by `MandrillSink` and `SNSSink`.

### _choose_color_html(level_name)

Maps log level name to an HTML hex color for email body styling.

### _format_subject(record, template, sink_name)

Formats email subject from a template string using record dict. Falls back to
`"{name} {level}"` on KeyError with a warning. Used by all 4 email sinks.
