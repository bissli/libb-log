import os
import tempfile
from pathlib import Path

from libb import Setting, expandabspath

Setting.unlock()  # temp

# Environment
HERE = os.path.abspath(os.path.dirname(__file__))
CHECKTTY = 'CONFIG_CHECKTTY' in os.environ

# Tmpdir
tmpdir = Setting()
if os.getenv('CONFIG_TMPDIR_DIR'):
    tmpdir.dir = expandabspath(os.getenv('CONFIG_TMPDIR_DIR'))
else:
    tmpdir.dir = tempfile.gettempdir()
Path(tmpdir.dir).mkdir(parents=True, exist_ok=True)

# Syslog
syslog = Setting()
syslog.host = os.getenv('CONFIG_SYSLOG_HOST')
syslog.port = os.getenv('CONFIG_SYSLOG_PORT')

# TLS Syslog
tlssyslog = Setting()
tlssyslog.host = os.getenv('CONFIG_TLSSYSLOG_HOST')
tlssyslog.port = os.getenv('CONFIG_TLSSYSLOG_PORT')
tlssyslog.dir = None
if os.getenv('CONFIG_TLSSYSLOG_DIR'):
    tlssyslog.dir = expandabspath(os.getenv('CONFIG_TLSSYSLOG_DIR'))

# Log additional settings (comma separated)
log = Setting()
log.modules.extra = os.getenv('CONFIG_LOG_MODULES_EXTRA', '')
log.modules.ignore = os.getenv('CONFIG_LOG_MODULES_IGNORE', '')
