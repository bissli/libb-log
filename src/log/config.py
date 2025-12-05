import os
from pathlib import Path

from libb import Setting, expandabspath, get_tempdir, is_tty

Setting.unlock()

# Environment
HERE = Path(Path(__file__).parent).resolve()
CHECKTTY = is_tty()

# Tmpdir
tmpdir = get_tempdir()

# Syslog
syslog = Setting()
syslog.host = os.getenv('CONFIG_SYSLOG_HOST')
syslog.port = int(os.getenv('CONFIG_SYSLOG_PORT', 0)) or None

# TLS Syslog
tlssyslog = Setting()
tlssyslog.host = os.getenv('CONFIG_TLSSYSLOG_HOST')
tlssyslog.port = int(os.getenv('CONFIG_TLSSYSLOG_PORT', 0)) or None
tlssyslog.dir = None
if os.getenv('CONFIG_TLSSYSLOG_DIR'):
    tlssyslog.dir = expandabspath(os.getenv('CONFIG_TLSSYSLOG_DIR'))

# Log additional settings (comma separated)
log = Setting()
log.modules.extra = os.getenv('CONFIG_LOG_MODULES_EXTRA', '')
log.modules.ignore = os.getenv('CONFIG_LOG_MODULES_IGNORE', '')
log.enable_diagnose = os.getenv('CONFIG_LOG_ENABLE_DIAGNOSE', '').lower() in {'1', 'true', 'yes'}

Setting.lock()
