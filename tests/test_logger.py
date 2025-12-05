"""Tests for log._logger module."""
from unittest.mock import MagicMock, patch

import pytest

from log._logger import Logger, get_logger


class TestLogger:

    def test_init_with_name(self):
        """Test Logger initializes with name."""
        logger = Logger(name='mylogger')
        assert logger._name == 'mylogger'

    def test_init_with_context(self):
        """Test Logger initializes with context."""
        logger = Logger(user='john', request_id='abc123')
        assert logger._context == {'user': 'john', 'request_id': 'abc123'}

    def test_init_with_name_and_context(self):
        """Test Logger initializes with both name and context."""
        logger = Logger(name='web', ip='192.168.1.1')
        assert logger._name == 'web'
        assert logger._context == {'ip': '192.168.1.1'}


class TestLoggerBind:

    def test_bind_returns_new_logger(self):
        """Test bind() returns a new Logger instance."""
        logger = Logger(name='test')
        bound = logger.bind(user='john')
        assert bound is not logger
        assert isinstance(bound, Logger)

    def test_bind_preserves_name(self):
        """Test bind() preserves the original name."""
        logger = Logger(name='mylogger')
        bound = logger.bind(key='value')
        assert bound._name == 'mylogger'

    def test_bind_adds_context(self):
        """Test bind() adds new context."""
        logger = Logger()
        bound = logger.bind(user='john', ip='127.0.0.1')
        assert bound._context == {'user': 'john', 'ip': '127.0.0.1'}

    def test_bind_merges_context(self):
        """Test bind() merges with existing context."""
        logger = Logger(user='john')
        bound = logger.bind(ip='127.0.0.1')
        assert bound._context == {'user': 'john', 'ip': '127.0.0.1'}

    def test_bind_overwrites_context(self):
        """Test bind() overwrites existing context keys."""
        logger = Logger(user='john')
        bound = logger.bind(user='jane')
        assert bound._context == {'user': 'jane'}

    def test_bind_does_not_modify_original(self):
        """Test bind() does not modify the original logger."""
        logger = Logger(user='john')
        logger.bind(user='jane', extra='value')
        assert logger._context == {'user': 'john'}

    def test_bind_chain(self):
        """Test multiple bind() calls can be chained."""
        logger = Logger(name='test')
        bound = logger.bind(a='1').bind(b='2').bind(c='3')
        assert bound._context == {'a': '1', 'b': '2', 'c': '3'}


class TestLoggerLogging:

    @patch('log._backend.get_backend')
    def test_debug_calls_backend(self, mock_get_backend):
        """Test debug() calls backend.log()."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        logger = Logger(name='test')
        logger.debug('test message')

        mock_backend.log.assert_called_once()
        call_args = mock_backend.log.call_args
        assert call_args[0][0] == 'DEBUG'
        assert call_args[0][1] == 'test message'

    @patch('log._backend.get_backend')
    def test_info_calls_backend(self, mock_get_backend):
        """Test info() calls backend.log()."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        logger = Logger()
        logger.info('info message')

        mock_backend.log.assert_called_once()
        assert mock_backend.log.call_args[0][0] == 'INFO'

    @patch('log._backend.get_backend')
    def test_warning_calls_backend(self, mock_get_backend):
        """Test warning() calls backend.log()."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        logger = Logger()
        logger.warning('warning message')

        mock_backend.log.assert_called_once()
        assert mock_backend.log.call_args[0][0] == 'WARNING'

    @patch('log._backend.get_backend')
    def test_error_calls_backend(self, mock_get_backend):
        """Test error() calls backend.log()."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        logger = Logger()
        logger.error('error message')

        mock_backend.log.assert_called_once()
        assert mock_backend.log.call_args[0][0] == 'ERROR'

    @patch('log._backend.get_backend')
    def test_critical_calls_backend(self, mock_get_backend):
        """Test critical() calls backend.log()."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        logger = Logger()
        logger.critical('critical message')

        mock_backend.log.assert_called_once()
        assert mock_backend.log.call_args[0][0] == 'CRITICAL'

    @patch('log._backend.get_backend')
    def test_exception_sets_exc_info(self, mock_get_backend):
        """Test exception() sets exc_info=True."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        logger = Logger()
        logger.exception('exception message')

        mock_backend.log.assert_called_once()
        call_kwargs = mock_backend.log.call_args[1]
        assert call_kwargs.get('exc_info') is True

    @patch('log._backend.get_backend')
    def test_log_passes_context(self, mock_get_backend):
        """Test logging passes context to backend."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        logger = Logger(user='john', ip='127.0.0.1')
        logger.info('test')

        call_kwargs = mock_backend.log.call_args[1]
        assert call_kwargs.get('context') == {'user': 'john', 'ip': '127.0.0.1'}

    @patch('log._backend.get_backend')
    def test_log_passes_name(self, mock_get_backend):
        """Test logging passes name to backend."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        logger = Logger(name='mylogger')
        logger.info('test')

        call_kwargs = mock_backend.log.call_args[1]
        assert call_kwargs.get('name') == 'mylogger'


class TestLoggerAliases:

    def test_warn_is_warning(self):
        """Test warn is an alias for warning."""
        assert Logger.warn is Logger.warning

    def test_fatal_is_critical(self):
        """Test fatal is an alias for critical."""
        assert Logger.fatal is Logger.critical


class TestGetLogger:

    def test_get_logger_returns_logger(self):
        """Test get_logger() returns a Logger instance."""
        logger = get_logger()
        assert isinstance(logger, Logger)

    def test_get_logger_with_name(self):
        """Test get_logger() accepts name."""
        logger = get_logger('mylogger')
        assert logger._name == 'mylogger'

    def test_get_logger_with_context(self):
        """Test get_logger() accepts context kwargs."""
        logger = get_logger(user='john', ip='127.0.0.1')
        assert logger._context == {'user': 'john', 'ip': '127.0.0.1'}

    def test_get_logger_with_name_and_context(self):
        """Test get_logger() accepts both name and context."""
        logger = get_logger('web', user='john')
        assert logger._name == 'web'
        assert logger._context == {'user': 'john'}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
