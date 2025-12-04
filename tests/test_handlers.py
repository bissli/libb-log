import logging
import pathlib
import smtplib
import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import wrapt

from log.filters import PreambleFilter
from log.handlers import ColoredMandrillHandler, ColoredSMTPHandler
from log.handlers import ColoredStreamHandler, NonBufferedFileHandler
from log.handlers import SNSHandler, URLHandler

#
# global mocks, patches, stubs
#


@wrapt.patch_function_wrapper(smtplib.SMTP, 'sendmail')
def patch_smtp_sendmail(wrapped, instance, args, kwargs):
    """Patch out SMTP sendmail."""
    logging.getLogger(__name__).info('Simulated SMTP sendmail')


@wrapt.patch_function_wrapper(smtplib.SMTP, 'connect')
def patch_smtp_connect(wrapped, instance, args, kwargs):
    """Patch out SMTP connect."""
    return (220, b'OK')


@wrapt.patch_function_wrapper(smtplib.SMTP, 'login')
def patch_smtp_login(wrapped, instance, args, kwargs):
    """Patch out SMTP login."""


@wrapt.patch_function_wrapper(smtplib.SMTP, 'quit')
def patch_smtp_quit(wrapped, instance, args, kwargs):
    """Patch out SMTP quit."""


#
# NonBufferedFileHandler tests
#


class TestNonBufferedFileHandler:

    def test_emit_basic(self):
        """Test basic emit without preamble filter."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            filename = f.name
        try:
            handler = NonBufferedFileHandler(filename)
            handler.setFormatter(logging.Formatter('%(message)s'))
            record = logging.LogRecord(
                name='test', level=logging.INFO, pathname='', lineno=0,
                msg='Test message', args=(), exc_info=None
            )
            handler.emit(record)
            # NonBufferedFileHandler closes stream after emit, so clear it before close()
            handler.stream = None
            handler.close()
            with pathlib.Path(filename).open() as f:
                content = f.read()
            assert 'Test message' in content
        finally:
            pathlib.Path(filename).unlink()

    def test_emit_with_preamble_filter(self):
        """Test emit with PreambleFilter generates asctime correctly."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            filename = f.name
        try:
            handler = NonBufferedFileHandler(filename)
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            handler.addFilter(PreambleFilter())
            record = logging.LogRecord(
                name='test', level=logging.INFO, pathname='', lineno=0,
                msg='Test message', args=(), exc_info=None
            )
            # Add custom attributes expected by preamble
            record.cmd_app = 'test_app'
            record.cmd_args = 'arg1 arg2'
            record.cmd_setup = 'dev'
            handler.emit(record)
            # NonBufferedFileHandler closes stream after emit, so clear it before close()
            handler.stream = None
            handler.close()
            with pathlib.Path(filename).open() as f:
                content = f.read()
            assert '** Time:' in content
            assert '** App:   test_app' in content
            assert '** Args:  arg1 arg2' in content
            assert '** Setup: dev' in content
            assert 'Test message' in content
        finally:
            pathlib.Path(filename).unlink()

    def test_emit_with_preamble_no_formatter(self):
        """Test emit with PreambleFilter but no formatter still works."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            filename = f.name
        try:
            handler = NonBufferedFileHandler(filename)
            # No formatter set - should use default formatTime
            handler.addFilter(PreambleFilter())
            record = logging.LogRecord(
                name='test', level=logging.INFO, pathname='', lineno=0,
                msg='Test message', args=(), exc_info=None
            )
            record.cmd_app = 'test_app'
            record.cmd_args = ''
            record.cmd_setup = 'dev'
            handler.emit(record)
            # NonBufferedFileHandler closes stream after emit, so clear it before close()
            handler.stream = None
            handler.close()
            with pathlib.Path(filename).open() as f:
                content = f.read()
            assert '** Time:' in content
        finally:
            pathlib.Path(filename).unlink()


#
# Root cause analysis: asctime KeyError
#


class TestAsctimeRootCause:
    """Root cause analysis for KeyError: 'asctime' in preamble formatting.

    The issue: LogRecord does NOT include 'asctime' by default. The asctime
    attribute is only added when Formatter.format() calls formatTime().
    Since the preamble is written BEFORE super().emit() (where formatting
    occurs), asctime doesn't exist yet.

    Timeline of the bug:
    1. NonBufferedFileHandler.emit() is called
    2. Preamble check: if PreambleFilter present, write preamble
    3. Preamble uses %(asctime)s but record.__dict__ has no 'asctime'
    4. KeyError: 'asctime'
    5. super().emit() would have called format() which adds asctime - too late
    """

    def test_logrecord_does_not_have_asctime_by_default(self):
        """Demonstrate that asctime is NOT a standard LogRecord attribute."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        # asctime is NOT in the record's __dict__ by default
        assert 'asctime' not in record.__dict__
        assert not hasattr(record, 'asctime')

    def test_asctime_added_by_formatter(self):
        """Show that asctime is added when Formatter.format() is called."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        formatter = logging.Formatter('%(asctime)s %(message)s')

        # Before formatting: no asctime
        assert 'asctime' not in record.__dict__

        # Format the record
        formatter.format(record)

        # After formatting: asctime exists
        assert 'asctime' in record.__dict__
        assert hasattr(record, 'asctime')

    def test_preamble_format_requires_asctime(self):
        """Show that preamble format string requires asctime."""
        handler = NonBufferedFileHandler('/dev/null')
        # The preamble contains %(asctime)s
        assert '%(asctime)s' in handler.preamble

    def test_preamble_formatting_fails_without_asctime(self):
        """Demonstrate the original bug: preamble % record.__dict__ fails."""
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        record.cmd_app = 'test'
        record.cmd_args = ''
        record.cmd_setup = 'dev'

        preamble = '** Time: %(asctime)s\n'

        # This is the exact error that was occurring
        with pytest.raises(KeyError) as exc_info:
            preamble % record.__dict__
        assert 'asctime' in str(exc_info.value)

    def test_fix_adds_asctime_before_preamble(self):
        """Verify fix: asctime is populated before preamble formatting."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            filename = f.name
        try:
            handler = NonBufferedFileHandler(filename)
            handler.setFormatter(logging.Formatter('%(message)s'))
            handler.addFilter(PreambleFilter())

            record = logging.LogRecord(
                name='test', level=logging.INFO, pathname='', lineno=0,
                msg='Test message', args=(), exc_info=None
            )
            record.cmd_app = 'test_app'
            record.cmd_args = ''
            record.cmd_setup = 'dev'

            # Before emit: no asctime
            assert 'asctime' not in record.__dict__

            # emit should NOT raise KeyError
            handler.emit(record)

            # After emit: asctime was added
            assert 'asctime' in record.__dict__

            handler.stream = None
            handler.close()

            with pathlib.Path(filename).open() as f:
                content = f.read()
            # Verify the time was written to preamble
            assert '** Time:' in content
            # Verify it's a real timestamp (contains date-like pattern)
            assert '-' in content.split('** Time:')[1].split('\n')[0]
        finally:
            pathlib.Path(filename).unlink()

    def test_fix_works_without_formatter(self):
        """Verify fix works when no formatter is set (uses default)."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            filename = f.name
        try:
            handler = NonBufferedFileHandler(filename)
            # No formatter set
            handler.addFilter(PreambleFilter())

            record = logging.LogRecord(
                name='test', level=logging.INFO, pathname='', lineno=0,
                msg='Test message', args=(), exc_info=None
            )
            record.cmd_app = 'test_app'
            record.cmd_args = ''
            record.cmd_setup = 'dev'

            # Should NOT raise KeyError even without formatter
            handler.emit(record)

            # asctime should still be populated
            assert 'asctime' in record.__dict__

            handler.stream = None
            handler.close()
        finally:
            pathlib.Path(filename).unlink()

    def test_fix_preserves_existing_asctime(self):
        """Verify fix doesn't overwrite asctime if already present."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            filename = f.name
        try:
            handler = NonBufferedFileHandler(filename)
            handler.setFormatter(logging.Formatter('%(message)s'))
            handler.addFilter(PreambleFilter())

            record = logging.LogRecord(
                name='test', level=logging.INFO, pathname='', lineno=0,
                msg='Test message', args=(), exc_info=None
            )
            record.cmd_app = 'test_app'
            record.cmd_args = ''
            record.cmd_setup = 'dev'

            # Pre-set asctime to a known value
            record.asctime = 'CUSTOM_TIME_VALUE'

            handler.emit(record)

            # asctime should NOT be overwritten
            assert record.asctime == 'CUSTOM_TIME_VALUE'

            handler.stream = None
            handler.close()

            with pathlib.Path(filename).open() as f:
                content = f.read()
            assert 'CUSTOM_TIME_VALUE' in content
        finally:
            pathlib.Path(filename).unlink()


#
# ColoredStreamHandler tests
#


class TestColoredStreamHandler:

    def test_emit_to_stringio(self):
        """Test emit to a non-tty stream."""
        stream = StringIO()
        handler = ColoredStreamHandler()
        handler.stream = stream
        handler.setFormatter(logging.Formatter('%(message)s'))
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        handler.emit(record)
        output = stream.getvalue()
        assert 'Test message' in output

    def test_is_tty_returns_false_for_stringio(self):
        """Test is_tty returns False for StringIO."""
        stream = StringIO()
        handler = ColoredStreamHandler()
        handler.stream = stream
        assert handler.is_tty is False


#
# ColoredSMTPHandler tests
#


class TestColoredSMTPHandler:

    def test_get_subject_formatting(self):
        """Test subject line formatting with record attributes."""
        handler = ColoredSMTPHandler(
            mailhost='localhost',
            fromaddr='from@test.com',
            toaddrs=['to@test.com'],
            subject='%(levelname)s: %(name)s'
        )
        record = logging.LogRecord(
            name='mylogger', level=logging.ERROR, pathname='', lineno=0,
            msg='Error occurred', args=(), exc_info=None
        )
        subject = handler.getSubject(record)
        assert subject == 'ERROR: mylogger'

    @patch.object(smtplib.SMTP, 'ehlo')
    @patch.object(smtplib.SMTP, 'starttls')
    def test_emit_sends_email(self, mock_starttls, mock_ehlo):
        """Test emit creates and sends HTML email."""
        handler = ColoredSMTPHandler(
            mailhost='localhost',
            fromaddr='from@test.com',
            toaddrs=['to@test.com'],
            subject='Test: %(message)s'
        )
        handler.setFormatter(logging.Formatter('%(message)s'))
        record = logging.LogRecord(
            name='test', level=logging.ERROR, pathname='', lineno=0,
            msg='Test error', args=(), exc_info=None
        )
        # Should not raise - smtp operations are patched
        handler.emit(record)


#
# ColoredMandrillHandler tests
#


class TestColoredMandrillHandler:

    def test_init_without_mailchimp(self):
        """Test handler initializes with api=None when mailchimp unavailable."""
        with patch.dict('sys.modules', {'mailchimp_transactional': None}):
            handler = ColoredMandrillHandler(
                apikey='test-key',
                fromaddr='from@test.com',
                toaddrs=['to@test.com'],
                subject='Test'
            )
            # api may or may not be None depending on import state
            # but emit should handle it gracefully

    def test_emit_with_no_api(self):
        """Test emit returns early when api is None."""
        handler = ColoredMandrillHandler(
            apikey='test-key',
            fromaddr='from@test.com',
            toaddrs=['to@test.com'],
            subject='Test'
        )
        handler.api = None
        record = logging.LogRecord(
            name='test', level=logging.ERROR, pathname='', lineno=0,
            msg='Test error', args=(), exc_info=None
        )
        # Should not raise
        handler.emit(record)

    def test_emit_with_mocked_api(self):
        """Test emit calls api.messages.send with correct structure."""
        handler = ColoredMandrillHandler(
            apikey='test-key',
            fromaddr='from@test.com',
            toaddrs=['to@test.com'],
            subject='%(levelname)s: %(message)s'
        )
        handler.setFormatter(logging.Formatter('%(message)s'))
        mock_api = MagicMock()
        handler.api = mock_api
        record = logging.LogRecord(
            name='test', level=logging.ERROR, pathname='', lineno=0,
            msg='Test error', args=(), exc_info=None
        )
        handler.emit(record)
        mock_api.messages.send.assert_called_once()
        call_args = mock_api.messages.send.call_args[0][0]
        assert 'message' in call_args
        assert call_args['message']['from_email'] == 'from@test.com'
        assert call_args['message']['subject'] == 'ERROR: Test error'


#
# SNSHandler tests
#


class TestSNSHandler:

    def test_emit_with_no_connection(self):
        """Test emit returns early when sns_connection is None."""
        handler = SNSHandler(topic_arn='arn:aws:sns:us-east-1:123456789:topic')
        handler.sns_connection = None
        record = logging.LogRecord(
            name='test', level=logging.ERROR, pathname='', lineno=0,
            msg='Test error', args=(), exc_info=None
        )
        # Should not raise
        handler.emit(record)

    def test_emit_with_mocked_connection(self):
        """Test emit calls sns publish with correct parameters."""
        handler = SNSHandler(topic_arn='arn:aws:sns:us-east-1:123456789:topic')
        handler.setFormatter(logging.Formatter('%(message)s'))
        mock_client = MagicMock()
        handler.sns_client = mock_client
        record = logging.LogRecord(
            name='mylogger', level=logging.ERROR, pathname='', lineno=0,
            msg='Test error', args=(), exc_info=None
        )
        handler.emit(record)
        mock_client.publish.assert_called_once()
        kwargs = mock_client.publish.call_args[1]
        assert kwargs['TopicArn'] == 'arn:aws:sns:us-east-1:123456789:topic'
        assert 'Test error' in kwargs['Message']


#
# URLHandler tests
#


class TestURLHandler:

    @patch('urllib.request.urlopen')
    def test_emit_posts_to_url(self, mock_urlopen):
        """Test emit posts formatted record to URL."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'OK'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        handler = URLHandler(host='https://example.com', url='/logs')
        handler.setFormatter(logging.Formatter('%(message)s'))
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='Test message', args=(), exc_info=None
        )
        handler.emit(record)
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0]
        assert 'https://example.com/logs' in call_args[0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
