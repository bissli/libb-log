import importlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

#
# tmpdir configuration tests
#


class TestTmpdirConfig:

    def test_tmpdir_default_is_system_tempdir(self):
        """Test tmpdir defaults to system temp directory."""
        with patch.dict(os.environ, {}, clear=True):
            # Need to remove CONFIG_TMPDIR_DIR to test default
            os.environ.pop('CONFIG_TMPDIR_DIR', None)
            # Re-import to get fresh config
            import log.config
            importlib.reload(log.config)
            assert log.config.tmpdir.dir == tempfile.gettempdir()

    def test_tmpdir_from_environment(self):
        """Test tmpdir uses CONFIG_TMPDIR_DIR environment variable."""
        test_dir = '/tmp/test_log_dir'
        with patch.dict(os.environ, {'CONFIG_TMPDIR_DIR': test_dir}):
            import log.config
            importlib.reload(log.config)
            # The expandabspath may modify the path
            assert test_dir in str(log.config.tmpdir.dir) or 'test_log_dir' in str(log.config.tmpdir.dir)

    def test_tmpdir_directory_exists(self):
        """Test tmpdir directory is created if it doesn't exist."""
        import log.config
        assert Path(log.config.tmpdir.dir).exists()


#
# syslog configuration tests
#


class TestSyslogConfig:

    def test_syslog_host_from_environment(self):
        """Test syslog host from CONFIG_SYSLOG_HOST."""
        with patch.dict(os.environ, {'CONFIG_SYSLOG_HOST': 'localhost'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.syslog.host == 'localhost'

    def test_syslog_host_none_when_not_set(self):
        """Test syslog host is None when not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('CONFIG_SYSLOG_HOST', None)
            import log.config
            importlib.reload(log.config)
            assert log.config.syslog.host is None

    def test_syslog_port_from_environment(self):
        """Test syslog port from CONFIG_SYSLOG_PORT."""
        with patch.dict(os.environ, {'CONFIG_SYSLOG_PORT': '514'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.syslog.port == 514

    def test_syslog_port_none_when_zero(self):
        """Test syslog port is None when set to 0."""
        with patch.dict(os.environ, {'CONFIG_SYSLOG_PORT': '0'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.syslog.port is None

    def test_syslog_port_none_when_not_set(self):
        """Test syslog port is None when not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('CONFIG_SYSLOG_PORT', None)
            import log.config
            importlib.reload(log.config)
            assert log.config.syslog.port is None


#
# tlssyslog configuration tests
#


class TestTlsSyslogConfig:

    def test_tlssyslog_host_from_environment(self):
        """Test TLS syslog host from CONFIG_TLSSYSLOG_HOST."""
        with patch.dict(os.environ, {'CONFIG_TLSSYSLOG_HOST': 'secure.example.com'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.tlssyslog.host == 'secure.example.com'

    def test_tlssyslog_port_from_environment(self):
        """Test TLS syslog port from CONFIG_TLSSYSLOG_PORT."""
        with patch.dict(os.environ, {'CONFIG_TLSSYSLOG_PORT': '6514'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.tlssyslog.port == 6514

    def test_tlssyslog_dir_from_environment(self):
        """Test TLS syslog dir from CONFIG_TLSSYSLOG_DIR."""
        with patch.dict(os.environ, {'CONFIG_TLSSYSLOG_DIR': '/etc/ssl/certs'}):
            import log.config
            importlib.reload(log.config)
            assert '/etc/ssl/certs' in str(log.config.tlssyslog.dir) or 'ssl' in str(log.config.tlssyslog.dir)

    def test_tlssyslog_dir_none_when_not_set(self):
        """Test TLS syslog dir is None when not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('CONFIG_TLSSYSLOG_DIR', None)
            import log.config
            importlib.reload(log.config)
            assert log.config.tlssyslog.dir is None


#
# log modules configuration tests
#


class TestLogModulesConfig:

    def test_log_modules_extra_from_environment(self):
        """Test extra log modules from CONFIG_LOG_MODULES_EXTRA."""
        with patch.dict(os.environ, {'CONFIG_LOG_MODULES_EXTRA': 'module1,module2'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.log.modules.extra == 'module1,module2'

    def test_log_modules_extra_default_empty(self):
        """Test extra log modules defaults to empty string."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('CONFIG_LOG_MODULES_EXTRA', None)
            import log.config
            importlib.reload(log.config)
            assert log.config.log.modules.extra == ''

    def test_log_modules_ignore_from_environment(self):
        """Test ignored log modules from CONFIG_LOG_MODULES_IGNORE."""
        with patch.dict(os.environ, {'CONFIG_LOG_MODULES_IGNORE': 'noisy_module'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.log.modules.ignore == 'noisy_module'

    def test_log_modules_ignore_default_empty(self):
        """Test ignored log modules defaults to empty string."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('CONFIG_LOG_MODULES_IGNORE', None)
            import log.config
            importlib.reload(log.config)
            assert log.config.log.modules.ignore == ''


class TestLogEnableDiagnoseConfig:

    def test_enable_diagnose_default_false(self):
        """Test enable_diagnose defaults to False."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('CONFIG_LOG_ENABLE_DIAGNOSE', None)
            import log.config
            importlib.reload(log.config)
            assert log.config.log.enable_diagnose is False

    def test_enable_diagnose_true_with_1(self):
        """Test enable_diagnose is True when set to '1'."""
        with patch.dict(os.environ, {'CONFIG_LOG_ENABLE_DIAGNOSE': '1'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.log.enable_diagnose is True

    def test_enable_diagnose_true_with_true(self):
        """Test enable_diagnose is True when set to 'true'."""
        with patch.dict(os.environ, {'CONFIG_LOG_ENABLE_DIAGNOSE': 'true'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.log.enable_diagnose is True

    def test_enable_diagnose_true_with_yes(self):
        """Test enable_diagnose is True when set to 'yes'."""
        with patch.dict(os.environ, {'CONFIG_LOG_ENABLE_DIAGNOSE': 'yes'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.log.enable_diagnose is True

    def test_enable_diagnose_case_insensitive(self):
        """Test enable_diagnose is case insensitive."""
        with patch.dict(os.environ, {'CONFIG_LOG_ENABLE_DIAGNOSE': 'TRUE'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.log.enable_diagnose is True

    def test_enable_diagnose_false_with_invalid(self):
        """Test enable_diagnose is False with invalid value."""
        with patch.dict(os.environ, {'CONFIG_LOG_ENABLE_DIAGNOSE': 'invalid'}):
            import log.config
            importlib.reload(log.config)
            assert log.config.log.enable_diagnose is False


#
# HERE constant tests
#


class TestHereConstant:

    def test_here_is_path(self):
        """Test HERE is a resolved Path."""
        import log.config
        assert isinstance(log.config.HERE, Path)
        assert log.config.HERE.is_absolute()

    def test_here_exists(self):
        """Test HERE points to existing directory."""
        import log.config
        assert log.config.HERE.exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
