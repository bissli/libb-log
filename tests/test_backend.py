"""Tests for log._backend module."""
import logging
from unittest.mock import MagicMock, patch

import pytest

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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
