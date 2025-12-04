import logging
from unittest.mock import MagicMock

import pytest

from log.loggers import StderrStreamLogger

#
# StderrStreamLogger tests
#


class TestStderrStreamLogger:

    def test_init_stores_logger(self):
        """Test __init__ stores the provided logger."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        assert stream_logger.logger is mock_logger

    def test_init_sets_info_level(self):
        """Test __init__ sets level to INFO."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        assert stream_logger.level == logging.INFO

    def test_init_empty_linebuf(self):
        """Test __init__ sets empty linebuf."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        assert stream_logger.linebuf == ''

    def test_write_logs_single_line(self):
        """Test write logs a single line."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        stream_logger.write('Hello world')
        mock_logger.log.assert_called_once_with(logging.INFO, 'Hello world')

    def test_write_logs_multiple_lines(self):
        """Test write logs each line separately."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        stream_logger.write('Line 1\nLine 2\nLine 3')
        assert mock_logger.log.call_count == 3
        mock_logger.log.assert_any_call(logging.INFO, 'Line 1')
        mock_logger.log.assert_any_call(logging.INFO, 'Line 2')
        mock_logger.log.assert_any_call(logging.INFO, 'Line 3')

    def test_write_strips_trailing_whitespace(self):
        """Test write strips trailing whitespace from lines."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        stream_logger.write('Test line   \n')
        mock_logger.log.assert_called_once_with(logging.INFO, 'Test line')

    def test_write_strips_trailing_newlines(self):
        """Test write strips trailing newlines before splitting."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        stream_logger.write('Line 1\nLine 2\n\n')
        # Trailing newlines are stripped, so only 2 lines
        assert mock_logger.log.call_count == 2

    def test_write_empty_string(self):
        """Test write with empty string does not log."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        stream_logger.write('')
        mock_logger.log.assert_not_called()

    def test_write_only_whitespace(self):
        """Test write with only whitespace does not log."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        stream_logger.write('   \n\n   ')
        mock_logger.log.assert_not_called()

    def test_isatty_returns_false(self):
        """Test isatty always returns False."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        assert stream_logger.isatty() is False

    def test_fileno_returns_none(self):
        """Test fileno always returns None."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)
        assert stream_logger.fileno() is None


class TestStderrStreamLoggerIntegration:

    def test_with_real_logger(self):
        """Test StderrStreamLogger with a real logger."""
        logger = logging.getLogger('test_stderr_stream')
        logger.setLevel(logging.DEBUG)
        handler = logging.handlers.MemoryHandler(capacity=100) if hasattr(logging, 'handlers') else MagicMock()

        # Use a list to capture log records
        logged_messages = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                logged_messages.append(record.getMessage())

        capture_handler = CaptureHandler()
        logger.addHandler(capture_handler)

        stream_logger = StderrStreamLogger(logger)
        stream_logger.write('Test message from stderr')

        assert 'Test message from stderr' in logged_messages

        logger.removeHandler(capture_handler)

    def test_as_stderr_replacement(self):
        """Test StderrStreamLogger can be used as stderr replacement."""
        mock_logger = MagicMock()
        stream_logger = StderrStreamLogger(mock_logger)

        # Simulate print to stderr
        stream_logger.write('Error: something went wrong\n')
        stream_logger.write('Details: more info\n')

        assert mock_logger.log.call_count == 2
        mock_logger.log.assert_any_call(logging.INFO, 'Error: something went wrong')
        mock_logger.log.assert_any_call(logging.INFO, 'Details: more info')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
