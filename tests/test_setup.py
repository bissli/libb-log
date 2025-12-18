"""Tests for log.setup module - loguru-based implementation."""
import importlib
import logging
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from log.setup import SetupType, class_logger, configure_logging
from log.setup import log_exception, patch_webdriver, set_level


#
# Windows colorama initialization tests
#


class TestWindowsColoramaInit:
    """Test colorama initialization on Windows platform."""

    def test_colorama_initialized_on_windows(self):
        """Test that colorama.just_fix_windows_console is called on Windows."""
        mock_colorama = MagicMock()

        with patch.dict(sys.modules, {'colorama': mock_colorama}):
            with patch.object(sys, 'platform', 'win32'):
                # Reload module to trigger initialization
                import log.setup
                importlib.reload(log.setup)

        mock_colorama.just_fix_windows_console.assert_called_once()

    def test_colorama_not_initialized_on_linux(self):
        """Test that colorama is not initialized on Linux."""
        mock_colorama = MagicMock()

        with patch.dict(sys.modules, {'colorama': mock_colorama}):
            with patch.object(sys, 'platform', 'linux'):
                import log.setup
                importlib.reload(log.setup)

        mock_colorama.just_fix_windows_console.assert_not_called()

    def test_colorama_not_initialized_on_darwin(self):
        """Test that colorama is not initialized on macOS."""
        mock_colorama = MagicMock()

        with patch.dict(sys.modules, {'colorama': mock_colorama}):
            with patch.object(sys, 'platform', 'darwin'):
                import log.setup
                importlib.reload(log.setup)

        mock_colorama.just_fix_windows_console.assert_not_called()

    def test_missing_colorama_does_not_raise_on_windows(self):
        """Test graceful handling when colorama is not installed on Windows."""
        # Remove colorama from modules to simulate ImportError
        modules_without_colorama = {k: v for k, v in sys.modules.items()
                                    if not k.startswith('colorama')}

        with patch.dict(sys.modules, modules_without_colorama, clear=True):
            # Make colorama import raise ImportError
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == 'colorama':
                    raise ImportError('No module named colorama')
                return original_import(name, *args, **kwargs)

            with patch.object(builtins, '__import__', mock_import):
                with patch.object(sys, 'platform', 'win32'):
                    import log.setup
                    # Should not raise - just silently skip colorama init
                    importlib.reload(log.setup)

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_console_sink_uses_colorize_none(self, mock_is_tty, mock_get_backend):
        """Test console sink uses colorize=None for auto-detection."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        configure_logging(setup='cmd', app='testapp')

        # Find console sink call (sys.stderr)
        add_sink_calls = mock_backend.add_sink.call_args_list
        console_calls = [c for c in add_sink_calls if c[0][0] == sys.stderr]
        assert len(console_calls) == 1

        # Verify colorize=None for auto-detection
        console_kwargs = console_calls[0][1]
        assert console_kwargs.get('colorize') is None

#
# set_level tests
#


class TestSetLevel:

    def setup_method(self):
        """Reset logging handlers before each test."""
        logging.root.handlers.clear()
        handler = logging.StreamHandler()
        logging.root.addHandler(handler)
        logging.root.setLevel(logging.DEBUG)

    def teardown_method(self):
        """Clean up handlers after each test."""
        logging.root.handlers.clear()

    def test_set_level_debug(self):
        """Test setting level to DEBUG."""
        set_level('debug')
        assert logging.root.level == logging.DEBUG

    def test_set_level_info(self):
        """Test setting level to INFO."""
        set_level('info')
        assert logging.root.level == logging.INFO

    def test_set_level_warning(self):
        """Test setting level to WARNING."""
        set_level('warning')
        assert logging.root.level == logging.WARNING

    def test_set_level_warn_alias(self):
        """Test setting level to WARN (alias for WARNING)."""
        set_level('warn')
        assert logging.root.level == logging.WARNING

    def test_set_level_error(self):
        """Test setting level to ERROR."""
        set_level('error')
        assert logging.root.level == logging.ERROR

    def test_set_level_critical(self):
        """Test setting level to CRITICAL."""
        set_level('critical')
        assert logging.root.level == logging.CRITICAL

    def test_set_level_case_insensitive(self):
        """Test level name is case insensitive."""
        set_level('DEBUG')
        assert logging.root.level == logging.DEBUG
        set_level('Info')
        assert logging.root.level == logging.INFO


#
# patch_webdriver tests
#


class TestPatchWebdriver:

    def test_patches_screenshot_sinks(self):
        """Test patch_webdriver patches screenshot sinks via module registry."""
        from log import setup
        from log.sinks import ScreenshotMandrillSink

        mock_webdriver = MagicMock()
        mock_logger = MagicMock()

        # Create a mock sink with set_webdriver method
        mock_sink = MagicMock(spec=ScreenshotMandrillSink)

        # Add to module registry
        setup._screenshot_sinks.append(mock_sink)
        try:
            patch_webdriver(mock_logger, mock_webdriver)
            mock_sink.set_webdriver.assert_called_once_with(mock_webdriver)
        finally:
            setup._screenshot_sinks.clear()

    def test_patches_legacy_handlers_on_logger(self):
        """Test patch_webdriver patches legacy handlers with webdriver attr."""
        mock_webdriver = MagicMock()
        mock_logger = MagicMock()
        mock_handler = MagicMock()
        mock_handler.webdriver = None
        mock_logger.handlers = [mock_handler]

        patch_webdriver(mock_logger, mock_webdriver)

        assert mock_handler.webdriver == mock_webdriver

    def test_ignores_handlers_without_webdriver_attr(self):
        """Test patch_webdriver ignores handlers without webdriver attribute."""
        mock_webdriver = MagicMock()
        mock_logger = MagicMock()
        mock_handler = MagicMock(spec=logging.StreamHandler)
        # StreamHandler doesn't have webdriver attribute
        del mock_handler.webdriver
        mock_logger.handlers = [mock_handler]

        # Should not raise
        patch_webdriver(mock_logger, mock_webdriver)


#
# class_logger tests
#


class TestClassLogger:

    def test_adds_logger_to_class(self):
        """Test class_logger adds logger attribute to class."""
        class TestClass:
            pass

        class_logger(TestClass)

        assert hasattr(TestClass, 'logger')
        assert isinstance(TestClass.logger, logging.Logger)

    def test_logger_name_includes_module_and_class(self):
        """Test logger name is module.classname."""
        class MyTestClass:
            pass

        class_logger(MyTestClass)

        expected_name = f'{MyTestClass.__module__}.MyTestClass'
        assert MyTestClass.logger.name == expected_name

    def test_adds_should_log_debug_method(self):
        """Test class_logger adds _should_log_debug method."""
        class TestClass:
            pass

        class_logger(TestClass)

        assert hasattr(TestClass, '_should_log_debug')
        instance = TestClass()
        assert callable(instance._should_log_debug)

    def test_adds_should_log_info_method(self):
        """Test class_logger adds _should_log_info method."""
        class TestClass:
            pass

        class_logger(TestClass)

        assert hasattr(TestClass, '_should_log_info')
        instance = TestClass()
        assert callable(instance._should_log_info)

    def test_enable_debug_sets_level(self):
        """Test enable='debug' sets logger level to DEBUG."""
        class TestClass:
            pass

        class_logger(TestClass, enable='debug')

        assert TestClass.logger.level == logging.DEBUG

    def test_enable_info_sets_level(self):
        """Test enable='info' sets logger level to INFO."""
        class TestClass:
            pass

        class_logger(TestClass, enable='info')

        assert TestClass.logger.level == logging.INFO


#
# log_exception tests
#


class TestLogException:

    def test_logs_exception_on_error(self):
        """Test log_exception logs when wrapped function raises."""
        mock_logger = MagicMock()

        @log_exception(mock_logger)
        def failing_function():
            raise ValueError('Test error')

        with pytest.raises(ValueError):
            failing_function()

        mock_logger.exception.assert_called_once()

    def test_returns_result_on_success(self):
        """Test log_exception returns result when function succeeds."""
        mock_logger = MagicMock()

        @log_exception(mock_logger)
        def successful_function():
            return 42

        result = successful_function()

        assert result == 42
        mock_logger.exception.assert_not_called()

    def test_reraises_exception(self):
        """Test log_exception re-raises the original exception."""
        mock_logger = MagicMock()

        @log_exception(mock_logger)
        def failing_function():
            raise RuntimeError('Original error')

        with pytest.raises(RuntimeError, match='Original error'):
            failing_function()

    def test_preserves_function_args(self):
        """Test log_exception passes args to wrapped function."""
        mock_logger = MagicMock()

        @log_exception(mock_logger)
        def add_numbers(a, b):
            return a + b

        result = add_numbers(2, 3)

        assert result == 5

    def test_preserves_function_kwargs(self):
        """Test log_exception passes kwargs to wrapped function."""
        mock_logger = MagicMock()

        @log_exception(mock_logger)
        def greet(name, greeting='Hello'):
            return f'{greeting}, {name}!'

        result = greet('World', greeting='Hi')

        assert result == 'Hi, World!'


#
# configure_logging tests
#


class TestConfigureLogging:

    def setup_method(self):
        """Reset logging before each test."""
        logging.root.handlers.clear()

    def teardown_method(self):
        """Clean up logging after each test."""
        logging.root.handlers.clear()

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_cmd_setup(self, mock_is_tty, mock_get_backend):
        """Test configure_logging with 'cmd' setup."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        configure_logging(setup='cmd', app='testapp')

        mock_backend.reset.assert_called_once()
        mock_backend.configure.assert_called_once()
        # Should add console sink for cmd
        assert mock_backend.add_sink.called

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_job_setup(self, mock_is_tty, mock_get_backend):
        """Test configure_logging with 'job' setup."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        configure_logging(setup='job', app='testapp')

        mock_backend.reset.assert_called_once()
        mock_backend.configure.assert_called_once()

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_web_setup(self, mock_is_tty, mock_get_backend):
        """Test configure_logging with 'web' setup."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        configure_logging(setup='web', app='testapp')

        mock_backend.reset.assert_called_once()
        mock_backend.configure.assert_called_once()

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=True)
    def test_configure_adds_console_when_tty(self, mock_is_tty, mock_get_backend):
        """Test configure_logging adds console sink when running in TTY."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        configure_logging(setup='job', app='testapp')

        # Console sink should be added when is_tty() returns True
        add_sink_calls = mock_backend.add_sink.call_args_list
        console_sinks = [c for c in add_sink_calls if c[0][0] == sys.stderr]
        assert len(console_sinks) > 0

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=True)
    def test_configure_tty_uses_debug_level(self, mock_is_tty, mock_get_backend):
        """Test console uses DEBUG level when running in TTY, regardless of preset."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        # Job preset has INFO level, but TTY should override to DEBUG
        configure_logging(setup='job', app='testapp')

        add_sink_calls = mock_backend.add_sink.call_args_list
        console_sinks = [c for c in add_sink_calls if c[0][0] == sys.stderr]
        assert len(console_sinks) == 1
        console_call = console_sinks[0]
        assert console_call[1]['level'] == 'DEBUG'

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_non_tty_uses_preset_level(self, mock_is_tty, mock_get_backend):
        """Test console uses preset level when not in TTY."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        # CMD preset has console=True with DEBUG level
        configure_logging(setup='cmd', app='testapp')

        add_sink_calls = mock_backend.add_sink.call_args_list
        console_sinks = [c for c in add_sink_calls if c[0][0] == sys.stderr]
        assert len(console_sinks) == 1
        console_call = console_sinks[0]
        # CMD preset level is DEBUG
        assert console_call[1]['level'] == 'DEBUG'

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_with_level_override(self, mock_is_tty, mock_get_backend):
        """Test configure_logging applies level override."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        configure_logging(setup='cmd', app='testapp', level='error')

        # Check that level was passed to add_sink
        add_sink_calls = mock_backend.add_sink.call_args_list
        for call in add_sink_calls:
            kwargs = call[1]
            if 'level' in kwargs and kwargs.get('colorize'):
                # Console sink should have overridden level
                assert kwargs['level'] == 'ERROR'


#
# SetupType enum tests
#


class TestSetupType:

    def test_setup_type_values(self):
        """Test SetupType enum has correct values."""
        assert SetupType.CMD.value == 'cmd'
        assert SetupType.JOB.value == 'job'
        assert SetupType.WEB.value == 'web'
        assert SetupType.TWD.value == 'twd'
        assert SetupType.SRP.value == 'srp'

    def test_setup_type_is_str(self):
        """Test SetupType inherits from str for backward compatibility."""
        assert isinstance(SetupType.CMD, str)
        assert SetupType.CMD == 'cmd'

    def test_setup_type_from_string(self):
        """Test SetupType can be created from string."""
        assert SetupType('cmd') == SetupType.CMD
        assert SetupType('job') == SetupType.JOB

    def test_setup_type_invalid_raises(self):
        """Test invalid setup type raises ValueError."""
        with pytest.raises(ValueError):
            SetupType('invalid')

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_accepts_enum(self, mock_is_tty, mock_get_backend):
        """Test configure_logging accepts SetupType enum."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        configure_logging(setup=SetupType.CMD, app='testapp')

        mock_backend.reset.assert_called_once()


#
# class_logger as decorator tests
#


class TestClassLoggerDecorator:

    def test_class_logger_returns_class(self):
        """Test class_logger returns the class for decorator use."""
        class TestClass:
            pass

        result = class_logger(TestClass)
        assert result is TestClass

    def test_class_logger_as_decorator(self):
        """Test class_logger can be used as decorator."""
        @class_logger
        class DecoratedClass:
            pass

        assert hasattr(DecoratedClass, 'logger')
        assert isinstance(DecoratedClass.logger, logging.Logger)


#
# web_context parameter tests
#


class TestWebContext:

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_with_web_context(self, mock_is_tty, mock_get_backend):
        """Test configure_logging accepts web_context parameter."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        ip_fn = lambda: '192.168.1.1'
        user_fn = lambda: 'testuser'
        web_context = {'ip_fn': ip_fn, 'user_fn': user_fn}

        configure_logging(setup='web', app='testapp', web_context=web_context)

        # Verify configure was called with a patcher
        mock_backend.configure.assert_called_once()
        call_kwargs = mock_backend.configure.call_args[1]
        assert 'patcher' in call_kwargs
        assert callable(call_kwargs['patcher'])


#
# LogConfig and PRESETS tests
#


class TestLogConfig:

    def test_presets_exist_for_all_setup_types(self):
        """Test that PRESETS has config for each SetupType."""
        from log.setup import PRESETS

        for setup_type in SetupType:
            assert setup_type in PRESETS
            config = PRESETS[setup_type]
            assert config.setup == setup_type

    def test_cmd_preset_has_console_enabled(self):
        """Test CMD preset enables console logging."""
        from log.setup import PRESETS

        config = PRESETS[SetupType.CMD]
        assert config.console is True
        assert config.level == 'DEBUG'

    def test_job_preset_has_sinks_enabled(self):
        """Test JOB preset enables appropriate sinks."""
        from log.setup import PRESETS

        config = PRESETS[SetupType.JOB]
        assert config.file is True
        assert config.mail is True
        assert config.syslog is True
        assert config.sns is True

    def test_web_preset_has_sinks_enabled(self):
        """Test WEB preset enables appropriate sinks."""
        from log.setup import PRESETS

        config = PRESETS[SetupType.WEB]
        assert config.file is True
        assert config.mail is True
        assert config.syslog is True
        assert config.sns is True


#
# stdlib interception tests
#


class TestStdlibInterception:

    @patch('log.setup.get_backend')
    @patch('log.setup.intercept_stdlib')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_sets_up_stdlib_interception(self, mock_is_tty, mock_intercept, mock_get_backend):
        """Test configure_logging sets up stdlib logging interception."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        configure_logging(setup='cmd', app='testapp')

        # Should intercept standard setup type loggers
        mock_intercept.assert_called()
        call_args = mock_intercept.call_args_list[0][0][0]
        assert 'cmd' in call_args
        assert 'job' in call_args
        assert 'web' in call_args


#
# extra_handlers backward compatibility tests
#


class TestExtraHandlers:

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_with_extra_handlers_dict(self, mock_is_tty, mock_get_backend):
        """Test configure_logging handles extra_handlers with dictConfig style."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        extra = {
            'custom_handler': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
            }
        }
        configure_logging(setup='job', app='testapp', extra_handlers=extra)

        # Should call add_sink for the extra handler
        assert mock_backend.add_sink.called

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=False)
    def test_configure_with_callable_handler(self, mock_is_tty, mock_get_backend):
        """Test configure_logging handles callable handler instances."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        mock_handler = MagicMock()
        extra = {
            'custom': mock_handler
        }
        configure_logging(setup='job', app='testapp', extra_handlers=extra)

        # Should add the callable directly as a sink
        add_sink_calls = mock_backend.add_sink.call_args_list
        handler_added = any(c[0][0] == mock_handler for c in add_sink_calls)
        assert handler_added


class TestTTYSinkDisabling:
    """Test that remote sinks are disabled in TTY mode."""

    @patch('log.setup._mail_configured', return_value=True)
    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=True)
    def test_tty_disables_mail_sink(self, mock_is_tty, mock_get_backend, mock_mail_configured):
        """Test mail sink is disabled when running in TTY mode."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        # JOB preset has mail=True, but TTY mode should disable it
        configure_logging(setup='job', app='testapp')

        # Mail sink should NOT be added despite preset having mail=True
        add_sink_calls = mock_backend.add_sink.call_args_list
        from log.sinks import ScreenshotMandrillSink
        mail_sinks = [c for c in add_sink_calls
                      if isinstance(c[0][0], ScreenshotMandrillSink)]
        assert len(mail_sinks) == 0

    @patch('log.setup._syslog_configured', return_value=True)
    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=True)
    def test_tty_disables_syslog_sink(self, mock_is_tty, mock_get_backend, mock_syslog_configured):
        """Test syslog sink is disabled when running in TTY mode."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        # JOB preset has syslog=True, but TTY mode should disable it
        configure_logging(setup='job', app='testapp')

        # Syslog sink should NOT be added
        add_sink_calls = mock_backend.add_sink.call_args_list
        from log.sinks import SyslogSink
        syslog_sinks = [c for c in add_sink_calls
                        if isinstance(c[0][0], SyslogSink)]
        assert len(syslog_sinks) == 0

    @patch('log.setup._tlssyslog_configured', return_value=True)
    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=True)
    def test_tty_disables_tlssyslog_sink(self, mock_is_tty, mock_get_backend, mock_tlssyslog_configured):
        """Test TLS syslog sink is disabled when running in TTY mode."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        # JOB preset has tlssyslog=True, but TTY mode should disable it
        configure_logging(setup='job', app='testapp')

        # TLS syslog sink should NOT be added
        add_sink_calls = mock_backend.add_sink.call_args_list
        from log.sinks import TLSSyslogSink
        tlssyslog_sinks = [c for c in add_sink_calls
                          if isinstance(c[0][0], TLSSyslogSink)]
        assert len(tlssyslog_sinks) == 0

    @patch('log.setup._sns_configured', return_value=True)
    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=True)
    def test_tty_disables_sns_sink(self, mock_is_tty, mock_get_backend, mock_sns_configured):
        """Test SNS sink is disabled when running in TTY mode."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        # JOB preset has sns=True, but TTY mode should disable it
        configure_logging(setup='job', app='testapp')

        # SNS sink should NOT be added
        add_sink_calls = mock_backend.add_sink.call_args_list
        from log.sinks import SNSSink
        sns_sinks = [c for c in add_sink_calls
                     if isinstance(c[0][0], SNSSink)]
        assert len(sns_sinks) == 0

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=True)
    def test_tty_allows_console_sink(self, mock_is_tty, mock_get_backend):
        """Test console sink is still allowed in TTY mode."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        # TTY mode should add console sink automatically
        configure_logging(setup='job', app='testapp')

        # Console sink should be added
        add_sink_calls = mock_backend.add_sink.call_args_list
        console_sinks = [c for c in add_sink_calls if c[0][0] == sys.stderr]
        assert len(console_sinks) > 0

    @patch('log.setup.get_backend')
    @patch('log.setup.is_tty', return_value=True)
    def test_tty_allows_file_sink(self, mock_is_tty, mock_get_backend):
        """Test file sink is still allowed in TTY mode."""
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        # JOB preset has file=True, and TTY mode allows file sinks
        configure_logging(setup='job', app='testapp')

        # File sink should be added (sink path contains .log)
        add_sink_calls = mock_backend.add_sink.call_args_list
        file_sinks = [c for c in add_sink_calls
                      if isinstance(c[0][0], str) and c[0][0].endswith('.log')]
        assert len(file_sinks) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
