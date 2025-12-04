import logging
import socket
from unittest.mock import patch

import pytest

from log.filters import MachineFilter, PreambleFilter, WebServerFilter

#
# MachineFilter tests
#


class TestMachineFilter:

    def test_filter_returns_true(self):
        """Test filter always returns True (allows record through)."""
        filter_ = MachineFilter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        result = filter_.filter(record)
        assert result is True

    def test_filter_adds_machine_attribute(self):
        """Test filter adds machine hostname to record."""
        filter_ = MachineFilter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert hasattr(record, 'machine')
        assert record.machine == socket.gethostname()

    def test_filter_machine_is_hostname(self):
        """Test machine attribute matches socket.gethostname()."""
        filter_ = MachineFilter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        expected_hostname = socket.gethostname()
        filter_.filter(record)
        assert record.machine == expected_hostname


#
# PreambleFilter tests
#


class TestPreambleFilter:

    def test_init_defaults(self):
        """Test PreambleFilter initializes with defaults."""
        filter_ = PreambleFilter()
        assert filter_.cmd_app == ''
        assert filter_.cmd_args == ''
        assert filter_.cmd_setup == ''
        assert filter_.cmd_status == 'succeeded'
        assert filter_.failno == 40

    def test_init_custom_values(self):
        """Test PreambleFilter initializes with custom values."""
        filter_ = PreambleFilter(
            app='myapp',
            args='--verbose',
            setup='prod',
            statuses=('ok', 'error'),
            failno=30
        )
        assert filter_.cmd_app == 'myapp'
        assert filter_.cmd_args == '--verbose'
        assert filter_.cmd_setup == 'prod'
        assert filter_.cmd_status == 'ok'
        assert filter_.failno == 30

    def test_filter_returns_true(self):
        """Test filter always returns True."""
        filter_ = PreambleFilter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        result = filter_.filter(record)
        assert result is True

    def test_filter_adds_cmd_attributes(self):
        """Test filter adds cmd_* attributes to record."""
        filter_ = PreambleFilter(app='testapp', args='arg1 arg2', setup='dev')
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.cmd_app == 'testapp'
        assert record.cmd_args == 'arg1 arg2'
        assert record.cmd_setup == 'dev'
        assert record.cmd_status == 'succeeded'

    def test_filter_sets_failure_status_on_error(self):
        """Test filter sets failure status when level >= failno."""
        filter_ = PreambleFilter(statuses=('ok', 'failed'))
        record = logging.LogRecord(
            name='test', level=logging.ERROR, pathname='', lineno=0,
            msg='Error message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.cmd_status == 'failed'
        # Status persists on filter instance
        assert filter_.cmd_status == 'failed'

    def test_filter_keeps_success_below_failno(self):
        """Test filter keeps success status when level < failno."""
        filter_ = PreambleFilter(statuses=('ok', 'failed'), failno=40)
        record = logging.LogRecord(
            name='test', level=logging.WARNING, pathname='', lineno=0,
            msg='Warning message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.cmd_status == 'ok'

    def test_filter_status_persists_after_failure(self):
        """Test once failed, status stays failed."""
        filter_ = PreambleFilter(statuses=('ok', 'failed'))
        # First record: error
        error_record = logging.LogRecord(
            name='test', level=logging.ERROR, pathname='', lineno=0,
            msg='Error', args=(), exc_info=None
        )
        filter_.filter(error_record)
        assert filter_.cmd_status == 'failed'
        # Second record: info (but status should stay failed)
        info_record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Info', args=(), exc_info=None
        )
        filter_.filter(info_record)
        assert info_record.cmd_status == 'failed'

    def test_filter_custom_failno(self):
        """Test custom failno threshold."""
        filter_ = PreambleFilter(statuses=('ok', 'failed'), failno=30)
        # WARNING level is 30, should trigger failure
        record = logging.LogRecord(
            name='test', level=logging.WARNING, pathname='', lineno=0,
            msg='Warning', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.cmd_status == 'failed'


#
# WebServerFilter tests
#


class TestWebServerFilter:

    def test_init_defaults(self):
        """Test WebServerFilter initializes with default lambdas."""
        filter_ = WebServerFilter()
        assert callable(filter_.ip_fn)
        assert callable(filter_.user_fn)
        assert filter_.ip_fn() == ''
        assert filter_.user_fn() == ''

    def test_init_custom_functions(self):
        """Test WebServerFilter initializes with custom functions."""
        ip_fn = lambda: '192.168.1.1'
        user_fn = lambda: 'testuser'
        filter_ = WebServerFilter(ip_fn=ip_fn, user_fn=user_fn)
        assert filter_.ip_fn() == '192.168.1.1'
        assert filter_.user_fn() == 'testuser'

    def test_filter_returns_true(self):
        """Test filter always returns True."""
        filter_ = WebServerFilter()
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        result = filter_.filter(record)
        assert result is True

    def test_filter_adds_empty_ip_when_no_ip(self):
        """Test filter sets empty ip when ip_fn returns empty."""
        filter_ = WebServerFilter(ip_fn=lambda: '')
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.ip == ''

    def test_filter_adds_empty_ip_when_none(self):
        """Test filter sets empty ip when ip_fn returns None."""
        filter_ = WebServerFilter(ip_fn=lambda: None)
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.ip == ''

    def test_filter_adds_user_attribute(self):
        """Test filter adds user attribute to record."""
        filter_ = WebServerFilter(user_fn=lambda: 'alice')
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.user == 'alice'

    def test_filter_adds_empty_user_when_none(self):
        """Test filter sets empty user when user_fn returns None."""
        filter_ = WebServerFilter(user_fn=lambda: None)
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.user == ''

    @patch('socket.gethostbyaddr')
    def test_filter_resolves_ip_to_hostname(self, mock_gethostbyaddr):
        """Test filter resolves IP address to hostname."""
        mock_gethostbyaddr.return_value = ('host.example.com', [], [])
        filter_ = WebServerFilter(ip_fn=lambda: '192.168.1.100')
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.ip == 'host.example.com'
        mock_gethostbyaddr.assert_called_once_with('192.168.1.100')

    @patch('socket.gethostbyaddr')
    def test_filter_uses_ip_on_resolution_failure(self, mock_gethostbyaddr):
        """Test filter uses IP when hostname resolution fails."""
        mock_gethostbyaddr.side_effect = OSError('DNS failure')
        filter_ = WebServerFilter(ip_fn=lambda: '10.0.0.1')
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        filter_.filter(record)
        assert record.ip == '10.0.0.1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
