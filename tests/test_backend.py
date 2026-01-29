"""Tests for log._backend module."""
import logging
from unittest.mock import MagicMock, patch

import pytest

import log._backend
from log._backend import InterceptHandler, get_backend, intercept_stdlib


class TestInterceptHandler:
    """Tests for InterceptHandler class."""

    def setup_method(self):
        """Reset logging before each test."""
        logging.root.handlers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        logging.root.handlers.clear()

    @patch('log._backend._loguru')
    def test_emit_forwards_to_loguru(self, mock_loguru):
        """Test emit forwards log record to loguru."""
        mock_bound = MagicMock()
        mock_loguru.bind.return_value = mock_bound
        mock_opt = MagicMock()
        mock_bound.opt.return_value = mock_opt
        mock_loguru.level.return_value.name = 'INFO'

        handler = InterceptHandler()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        mock_loguru.bind.assert_called_once()
        mock_opt.log.assert_called_once()

    @patch('log._backend._loguru')
    def test_emit_handles_formatting_error_type_error(self, mock_loguru):
        """Test emit handles TypeError from mismatched format args."""
        mock_bound = MagicMock()
        mock_loguru.bind.return_value = mock_bound
        mock_opt = MagicMock()
        mock_bound.opt.return_value = mock_opt
        mock_loguru.level.return_value.name = 'INFO'

        handler = InterceptHandler()
        # Create record with mismatched args (too many args for format string)
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Message with %s',
            args=('arg1', 'arg2', 'extra_arg'),  # Too many args
            exc_info=None,
        )

        # Should not raise
        handler.emit(record)

        # Should have logged with fallback message
        mock_opt.log.assert_called_once()
        call_args = mock_opt.log.call_args
        logged_msg = call_args[0][1]
        assert 'Message with %s' in logged_msg
        assert 'arg1' in logged_msg
        assert 'arg2' in logged_msg

    @patch('log._backend._loguru')
    def test_emit_handles_formatting_error_value_error(self, mock_loguru):
        """Test emit handles ValueError from invalid format specifier."""
        mock_bound = MagicMock()
        mock_loguru.bind.return_value = mock_bound
        mock_opt = MagicMock()
        mock_bound.opt.return_value = mock_opt
        mock_loguru.level.return_value.name = 'INFO'

        handler = InterceptHandler()
        # Create record with incomplete format specifier (missing type)
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Value is %',  # Incomplete format specifier
            args=('unused',),
            exc_info=None,
        )

        # Should not raise
        handler.emit(record)

        # Should have logged with fallback
        mock_opt.log.assert_called_once()
        call_args = mock_opt.log.call_args
        logged_msg = call_args[0][1]
        assert 'Value is %' in logged_msg

    @patch('log._backend._loguru')
    def test_emit_handles_no_args_on_format_error(self, mock_loguru):
        """Test emit fallback when format fails but no args present."""
        mock_bound = MagicMock()
        mock_loguru.bind.return_value = mock_bound
        mock_opt = MagicMock()
        mock_bound.opt.return_value = mock_opt
        mock_loguru.level.return_value.name = 'INFO'

        handler = InterceptHandler()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Simple message',
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        mock_opt.log.assert_called_once()
        call_args = mock_opt.log.call_args
        logged_msg = call_args[0][1]
        assert logged_msg == 'Simple message'

    @patch('log._backend._loguru')
    def test_emit_binds_logger_name(self, mock_loguru):
        """Test emit binds the logger name from record."""
        mock_bound = MagicMock()
        mock_loguru.bind.return_value = mock_bound
        mock_opt = MagicMock()
        mock_bound.opt.return_value = mock_opt
        mock_loguru.level.return_value.name = 'INFO'

        handler = InterceptHandler()
        record = logging.LogRecord(
            name='my.custom.logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test',
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        mock_loguru.bind.assert_called_once_with(logger_name='my.custom.logger')

    @patch('log._backend._loguru')
    def test_emit_handles_unknown_level(self, mock_loguru):
        """Test emit handles unknown log level gracefully."""
        mock_bound = MagicMock()
        mock_loguru.bind.return_value = mock_bound
        mock_opt = MagicMock()
        mock_bound.opt.return_value = mock_opt
        mock_loguru.level.side_effect = ValueError('Unknown level')

        handler = InterceptHandler()
        record = logging.LogRecord(
            name='test',
            level=42,  # Custom level
            pathname='test.py',
            lineno=1,
            msg='Test',
            args=(),
            exc_info=None,
        )
        record.levelname = 'CUSTOM'

        handler.emit(record)

        # Should fall back to numeric level
        mock_opt.log.assert_called_once()
        call_args = mock_opt.log.call_args
        assert call_args[0][0] == 42  # Numeric level

    @patch('log._backend._loguru')
    def test_emit_passes_exception_info(self, mock_loguru):
        """Test emit passes exception info to loguru."""
        mock_bound = MagicMock()
        mock_loguru.bind.return_value = mock_bound
        mock_opt = MagicMock()
        mock_bound.opt.return_value = mock_opt
        mock_loguru.level.return_value.name = 'ERROR'

        handler = InterceptHandler()

        try:
            raise ValueError('Test exception')
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name='test',
            level=logging.ERROR,
            pathname='test.py',
            lineno=1,
            msg='Error occurred',
            args=(),
            exc_info=exc_info,
        )

        handler.emit(record)

        # Verify opt was called with exception info
        mock_bound.opt.assert_called_once()
        opt_kwargs = mock_bound.opt.call_args[1]
        assert opt_kwargs['exception'] == exc_info


class TestInterceptStdlib:
    """Tests for intercept_stdlib function."""

    def setup_method(self):
        """Reset logging before each test."""
        logging.root.handlers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        logging.root.handlers.clear()
        # Reset any named loggers we created
        for name in ['test_logger', 'another_logger']:
            logger = logging.getLogger(name)
            logger.handlers.clear()
            logger.propagate = True

    def test_intercept_sets_root_handler(self):
        """Test intercept_stdlib sets up root logger handler."""
        intercept_stdlib()

        assert len(logging.root.handlers) == 1
        assert isinstance(logging.root.handlers[0], InterceptHandler)

    def test_intercept_named_loggers(self):
        """Test intercept_stdlib sets up named logger handlers."""
        intercept_stdlib(['test_logger', 'another_logger'])

        test_logger = logging.getLogger('test_logger')
        another_logger = logging.getLogger('another_logger')

        assert len(test_logger.handlers) == 1
        assert isinstance(test_logger.handlers[0], InterceptHandler)
        assert len(another_logger.handlers) == 1
        assert isinstance(another_logger.handlers[0], InterceptHandler)

    def test_intercept_disables_propagation(self):
        """Test intercept_stdlib disables propagation for named loggers."""
        intercept_stdlib(['test_logger'])

        test_logger = logging.getLogger('test_logger')
        assert test_logger.propagate is False

    def test_intercept_sets_debug_level(self):
        """Test intercept_stdlib sets DEBUG level on named loggers."""
        intercept_stdlib(['test_logger'])

        test_logger = logging.getLogger('test_logger')
        assert test_logger.level == logging.DEBUG


class TestGetBackend:
    """Tests for get_backend function."""

    def test_returns_singleton(self):
        """Test get_backend returns same instance."""
        backend1 = get_backend()
        backend2 = get_backend()

        assert backend1 is backend2

    def test_backend_has_required_methods(self):
        """Test backend has all required public methods."""
        backend = get_backend()

        assert hasattr(backend, 'log')
        assert hasattr(backend, 'add_sink')
        assert hasattr(backend, 'remove_sink')
        assert hasattr(backend, 'reset')
        assert hasattr(backend, 'configure')
        assert hasattr(backend, 'complete')


class TestModuleFilter:
    """Tests for whitelist module filtering at sink level."""

    def setup_method(self):
        """Reset cache before each test."""
        log._backend._reset_module_cache()

    def teardown_method(self):
        """Clean up after each test."""
        log._backend._reset_module_cache()

    def _make_record(self, name: str, level_no: int = 20, logger_name: str = '') -> dict:
        """Create a mock loguru record."""
        record = {
            'name': name,
            'level': MagicMock(no=level_no),
            'extra': {},
            }
        if logger_name:
            record['extra']['logger_name'] = logger_name
        return record

    @patch('log._backend.config_log')
    def test_filter_allows_base_module(self, mock_config):
        """Verify filter allows base modules (cmd, job, web, etc)."""
        mock_config.log.modules.extra = ''

        from log._backend import _module_filter

        assert _module_filter(self._make_record('cmd')) is True
        assert _module_filter(self._make_record('job')) is True
        assert _module_filter(self._make_record('web')) is True
        assert _module_filter(self._make_record('twd')) is True
        assert _module_filter(self._make_record('srp')) is True
        assert _module_filter(self._make_record('log')) is True

    @patch('log._backend.config_log')
    def test_filter_allows_child_of_base_module(self, mock_config):
        """Verify filter allows child modules of base modules."""
        mock_config.log.modules.extra = ''

        from log._backend import _module_filter

        assert _module_filter(self._make_record('web.forms.investor')) is True
        assert _module_filter(self._make_record('job.runner')) is True
        assert _module_filter(self._make_record('log._backend')) is True

    @patch('log._backend.config_log')
    def test_filter_blocks_unlisted_module_debug(self, mock_config):
        """Verify filter blocks debug/info from unlisted modules."""
        mock_config.log.modules.extra = ''

        from log._backend import _module_filter

        assert _module_filter(self._make_record('cachu', level_no=10)) is False
        assert _module_filter(self._make_record('urllib3', level_no=20)) is False
        assert _module_filter(self._make_record('requests.api', level_no=30)) is False

    @patch('log._backend.config_log')
    def test_filter_allows_unlisted_module_error(self, mock_config):
        """Verify filter allows ERROR+ from any module."""
        mock_config.log.modules.extra = ''

        from log._backend import _module_filter

        assert _module_filter(self._make_record('cachu', level_no=40)) is True
        assert _module_filter(self._make_record('urllib3', level_no=50)) is True

    @patch('log._backend.config_log')
    def test_filter_allows_extra_modules(self, mock_config):
        """Verify filter allows modules from CONFIG_LOG_MODULES_EXTRA."""
        mock_config.log.modules.extra = 'tc,myapp'

        from log._backend import _module_filter

        assert _module_filter(self._make_record('tc')) is True
        assert _module_filter(self._make_record('tc.finance')) is True
        assert _module_filter(self._make_record('myapp.core')) is True

    @patch('log._backend.config_log')
    def test_filter_handles_whitespace_in_extra(self, mock_config):
        """Verify filter handles whitespace in extra modules list."""
        mock_config.log.modules.extra = 'tc , myapp'

        from log._backend import _module_filter

        assert _module_filter(self._make_record('tc')) is True
        assert _module_filter(self._make_record('myapp')) is True

    @patch('log._backend.config_log')
    def test_filter_checks_logger_name_in_extra(self, mock_config):
        """Verify filter checks extra['logger_name'] for stdlib intercepts."""
        mock_config.log.modules.extra = ''

        from log._backend import _module_filter

        # When module name is not in whitelist, check logger_name
        record = self._make_record('some.internal.module', logger_name='web.forms')
        assert _module_filter(record) is True

        record = self._make_record('some.internal.module', logger_name='cachu')
        assert _module_filter(record) is False

    @patch('log._backend.config_log')
    def test_filter_error_passthrough_via_logger_name(self, mock_config):
        """Verify error passthrough works for stdlib intercepts."""
        mock_config.log.modules.extra = ''

        from log._backend import _module_filter

        record = self._make_record('log._backend', level_no=40, logger_name='cachu')
        assert _module_filter(record) is True


class TestAddSinkFilter:
    """Tests for filter application in add_sink."""

    def setup_method(self):
        """Reset cache before each test."""
        log._backend._reset_module_cache()

    def teardown_method(self):
        """Clean up after each test."""
        log._backend._reset_module_cache()

    @patch('log._backend.config_log')
    @patch('log._backend._loguru')
    def test_add_sink_applies_module_filter(self, mock_loguru, mock_config):
        """Verify add_sink applies _module_filter by default."""
        mock_config.log.modules.extra = ''
        mock_loguru.add.return_value = 1

        from log._backend import LoguruBackend, _module_filter
        backend = LoguruBackend()
        backend.add_sink('test_sink', level='INFO')

        mock_loguru.add.assert_called_once()
        call_kwargs = mock_loguru.add.call_args[1]
        assert call_kwargs['filter'] is _module_filter

    @patch('log._backend.config_log')
    @patch('log._backend._loguru')
    def test_add_sink_composes_user_filter(self, mock_loguru, mock_config):
        """Verify add_sink composes user filter with module filter."""
        mock_config.log.modules.extra = ''
        mock_loguru.add.return_value = 1

        user_filter = MagicMock(return_value=True)

        from log._backend import LoguruBackend
        backend = LoguruBackend()
        backend.add_sink('test_sink', filter=user_filter)

        mock_loguru.add.assert_called_once()
        call_kwargs = mock_loguru.add.call_args[1]
        composed = call_kwargs['filter']

        # Test composed filter blocks unlisted modules (whitelist)
        log._backend._reset_module_cache()
        record = {'name': 'cachu', 'level': MagicMock(no=20), 'extra': {}}
        result = composed(record)
        assert result is False
        user_filter.assert_not_called()

        # Test composed filter allows whitelisted modules and calls user filter
        log._backend._reset_module_cache()
        record = {'name': 'web.forms', 'level': MagicMock(no=20), 'extra': {}}
        result = composed(record)
        assert result is True
        user_filter.assert_called_once()

    @patch('log._backend.config_log')
    @patch('log._backend._loguru')
    def test_add_sink_preserves_string_filter(self, mock_loguru, mock_config):
        """Verify add_sink preserves string filter (advanced use case)."""
        mock_config.log.modules.extra = ''
        mock_loguru.add.return_value = 1

        from log._backend import LoguruBackend
        backend = LoguruBackend()
        backend.add_sink('test_sink', filter='myapp')

        mock_loguru.add.assert_called_once()
        call_kwargs = mock_loguru.add.call_args[1]
        assert call_kwargs['filter'] == 'myapp'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
