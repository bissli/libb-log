"""Tests for log.sinks module."""
from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from log.sinks import MandrillSink, ScreenshotMandrillSink, SMTPSink
from log.sinks import _format_subject, warn_once_if_none


def _make_record(**overrides):
    """Build a minimal loguru record dict for testing."""
    record = {
        'name': 'test',
        'level': SimpleNamespace(name='ERROR', no=40),
        'extra': {'machine': 'host1'},
        }
    record.update(overrides)
    return record


def _make_message(record=None, text='test message'):
    """Build a fake loguru Message (str subclass with .record)."""
    msg = MagicMock(spec=str)
    msg.record = record or _make_record()
    msg.__str__ = MagicMock(return_value=text)
    return msg


class TestFormatSubject:
    """Tests for _format_subject helper."""

    @patch('log.sinks._loguru')
    def test_normal_formatting(self, mock_loguru):
        """Verify template is formatted with record fields."""
        record = _make_record()
        result = _format_subject(record, '{name} {level.name}', 'TestSink')
        assert result == 'test ERROR'

    @patch('log.sinks._loguru')
    def test_keyerror_fallback(self, mock_loguru):
        """Verify fallback string on missing template key."""
        record = _make_record()
        result = _format_subject(record, '{missing_key}', 'TestSink')
        assert result == 'test ERROR'
        mock_loguru.opt.return_value.warning.assert_called_once()

    @patch('log.sinks._loguru')
    def test_fallback_uses_name_from_record(self, mock_loguru):
        """Verify fallback uses record name, not hardcoded."""
        record = _make_record(name='myapp')
        result = _format_subject(record, '{no_such_key}', 'TestSink')
        assert result == 'myapp ERROR'

    @patch('log.sinks._loguru')
    def test_fallback_default_name(self, mock_loguru):
        """Verify fallback defaults to 'log' when name missing."""
        record = _make_record()
        del record['name']
        result = _format_subject(record, '{no_such_key}', 'TestSink')
        assert result == 'log ERROR'


class TestSMTPSinkSend:
    """Tests for SMTPSink._send method."""

    def _make_sink(self, **overrides):
        """Create an SMTPSink with test defaults."""
        kwargs = {
            'mailhost': 'smtp.test.com',
            'port': 587,
            'fromaddr': 'from@test.com',
            'toaddrs': ['to@test.com'],
            }
        kwargs.update(overrides)
        return SMTPSink(**kwargs)

    @patch('log.sinks.smtplib')
    def test_plain_smtp(self, mock_smtplib):
        """Verify plain SMTP connection flow."""
        sink = self._make_sink()
        mock_smtp = MagicMock()
        mock_smtplib.SMTP.return_value = mock_smtp
        msg = MagicMock()

        sink._send(msg)

        mock_smtplib.SMTP.assert_called_once_with('smtp.test.com', 587)
        mock_smtp.sendmail.assert_called_once()
        mock_smtp.quit.assert_called_once()
        mock_smtp.ehlo.assert_not_called()
        mock_smtp.login.assert_not_called()

    @patch('log.sinks.smtplib')
    def test_ssl_smtp(self, mock_smtplib):
        """Verify SSL connection uses SMTP_SSL."""
        sink = self._make_sink(ssl=True)
        mock_smtp = MagicMock()
        mock_smtplib.SMTP_SSL.return_value = mock_smtp
        msg = MagicMock()

        sink._send(msg)

        mock_smtplib.SMTP_SSL.assert_called_once_with('smtp.test.com', 587)
        mock_smtplib.SMTP.assert_not_called()

    @patch('log.sinks.smtplib')
    def test_starttls_flow(self, mock_smtplib):
        """Verify STARTTLS calls ehlo/starttls/ehlo sequence."""
        sink = self._make_sink(starttls=True)
        mock_smtp = MagicMock()
        mock_smtplib.SMTP.return_value = mock_smtp
        msg = MagicMock()

        sink._send(msg)

        assert mock_smtp.ehlo.call_count == 2
        mock_smtp.starttls.assert_called_once()

    @patch('log.sinks.smtplib')
    def test_auth_when_username_set(self, mock_smtplib):
        """Verify login called when username provided."""
        sink = self._make_sink(username='user', password='pass')
        mock_smtp = MagicMock()
        mock_smtplib.SMTP.return_value = mock_smtp
        msg = MagicMock()

        sink._send(msg)

        mock_smtp.login.assert_called_once_with('user', 'pass')

    @patch('log.sinks.smtplib')
    def test_no_auth_when_no_username(self, mock_smtplib):
        """Verify login not called when no username."""
        sink = self._make_sink()
        mock_smtp = MagicMock()
        mock_smtplib.SMTP.return_value = mock_smtp
        msg = MagicMock()

        sink._send(msg)

        mock_smtp.login.assert_not_called()


class TestMandrillSinkCall:
    """Tests for MandrillSink.__call__ behavior."""

    @patch('log.sinks.HAS_MAILCHIMP', True)
    @patch('log.sinks.MailchimpTransactional')
    @patch('log.sinks._loguru')
    def test_sends_email_dict(self, mock_loguru, mock_mc):
        """Verify API call with correct email dict structure."""
        mock_client = MagicMock()
        mock_mc.Client.return_value = mock_client
        sink = MandrillSink(
            apikey='key',
            fromaddr='from@test.com',
            toaddrs='to@test.com',
            subject_template='{name} {level.name}')

        message = _make_message()
        sink(message)

        mock_client.messages.send.assert_called_once()
        sent_msg = mock_client.messages.send.call_args[0][0]['message']
        assert sent_msg['from_email'] == 'from@test.com'
        assert sent_msg['to'] == [{'email': 'to@test.com'}]
        assert sent_msg['subject'] == 'test ERROR'
        assert 'html' in sent_msg
        assert 'text' in sent_msg

    @patch('log.sinks._loguru')
    def test_warn_once_if_none_returns_none(self, mock_loguru):
        """Verify returns None when api is None."""
        sink = MandrillSink.__new__(MandrillSink)
        sink.api = None
        sink.subject_template = '{name}'

        result = sink(_make_message())
        assert result is None

    @patch('log.sinks._loguru')
    def test_warn_once_if_none_warns_once(self, mock_loguru):
        """Verify warning fires exactly once across multiple calls."""
        @warn_once_if_none('val', 'test warning')
        def guarded(self):
            return 'ok'

        obj = SimpleNamespace(val=None)
        guarded(obj)
        guarded(obj)
        guarded(obj)

        warning_calls = [
            c for c in mock_loguru.opt.return_value.warning.call_args_list
            if c == call('test warning')
            ]
        assert len(warning_calls) == 1


class TestScreenshotMandrillSinkCall:
    """Tests for ScreenshotMandrillSink fallback behavior."""

    @patch('log.sinks.HAS_MAILCHIMP', True)
    @patch('log.sinks.MailchimpTransactional')
    @patch('log.sinks._loguru')
    def test_fallback_when_no_webdriver(self, mock_loguru, mock_mc):
        """Verify falls back to parent __call__ when webdriver is None."""
        mock_client = MagicMock()
        mock_mc.Client.return_value = mock_client
        sink = ScreenshotMandrillSink(
            apikey='key',
            fromaddr='from@test.com',
            toaddrs='to@test.com',
            subject_template='{name} {level.name}')

        message = _make_message()
        sink(message)

        mock_client.messages.send.assert_called_once()
        sent_msg = mock_client.messages.send.call_args[0][0]['message']
        assert 'images' not in sent_msg

    @patch('log.sinks.HAS_MAILCHIMP', True)
    @patch('log.sinks.MailchimpTransactional')
    @patch('log.sinks._loguru')
    def test_attaches_screenshot_with_webdriver(self, mock_loguru, mock_mc):
        """Verify screenshot and page source attached when webdriver set."""
        mock_client = MagicMock()
        mock_mc.Client.return_value = mock_client

        mock_webdriver = MagicMock()
        mock_webdriver.current_url = 'http://test.com'
        screenshot_b64 = base64.b64encode(b'fake-png').decode('ascii')
        mock_webdriver.get_screenshot_as_base64.return_value = screenshot_b64
        mock_webdriver.page_source = '<html>test</html>'

        sink = ScreenshotMandrillSink(
            apikey='key',
            fromaddr='from@test.com',
            toaddrs='to@test.com',
            subject_template='{name} {level.name}',
            webdriver=mock_webdriver)

        message = _make_message()
        sink(message)

        mock_client.messages.send.assert_called_once()
        sent_msg = mock_client.messages.send.call_args[0][0]['message']
        assert 'images' in sent_msg
        assert sent_msg['images'][0]['name'] == 'screenshot.png'
        assert 'attachments' in sent_msg
        assert sent_msg['attachments'][0]['name'] == 'page_source.txt'


class TestWarnOnceIfNone:
    """Tests for warn_once_if_none decorator."""

    @patch('log.sinks._loguru')
    def test_passes_through_when_attr_not_none(self, mock_loguru):
        """Verify decorated function runs when attribute is not None."""
        @warn_once_if_none('val', 'missing')
        def fn(self):
            return 'result'

        obj = SimpleNamespace(val='present')
        assert fn(obj) == 'result'

    @patch('log.sinks._loguru')
    def test_cross_instance_shared_warning(self, mock_loguru):
        """Verify warning state is shared across instances."""
        @warn_once_if_none('val', 'shared warning')
        def fn(self):
            return 'ok'

        obj_a = SimpleNamespace(val=None)
        obj_b = SimpleNamespace(val=None)
        fn(obj_a)
        fn(obj_b)

        warning_calls = [
            c for c in mock_loguru.opt.return_value.warning.call_args_list
            if c == call('shared warning')
            ]
        assert len(warning_calls) == 1
