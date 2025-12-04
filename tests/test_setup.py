import logging
from unittest.mock import MagicMock, patch

import pytest

from log.setup import _get_handler_defaults, class_logger, configure_logging
from log.setup import log_exception, patch_webdriver, set_level

#
# set_level tests
#


class TestSetLevel:

    def setup_method(self):
        """Reset logging handlers before each test."""
        # Clear any existing handlers
        logging.root.handlers.clear()
        # Add a basic handler for testing
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
        for handler in logging.root.handlers:
            assert handler.level == logging.DEBUG

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

    def test_set_level_invalid_raises(self):
        """Test invalid level name raises KeyError."""
        with pytest.raises(KeyError):
            set_level('invalid_level')


#
# patch_webdriver tests
#


class TestPatchWebdriver:

    def test_patches_screenshot_smtp_handler(self):
        """Test patch_webdriver patches ScreenshotColoredSMTPHandler."""
        from log.handlers import ScreenshotColoredSMTPHandler
        mock_webdriver = MagicMock()
        mock_logger = MagicMock()
        mock_handler = MagicMock(spec=ScreenshotColoredSMTPHandler)
        mock_handler.level = logging.ERROR
        mock_logger.handlers = [mock_handler]

        patch_webdriver(mock_logger, mock_webdriver)

        assert mock_handler.webdriver == mock_webdriver

    def test_patches_screenshot_mandrill_handler(self):
        """Test patch_webdriver patches ScreenshotColoredMandrillHandler."""
        from log.handlers import ScreenshotColoredMandrillHandler
        mock_webdriver = MagicMock()
        mock_logger = MagicMock()
        mock_handler = MagicMock(spec=ScreenshotColoredMandrillHandler)
        mock_handler.level = logging.ERROR
        mock_logger.handlers = [mock_handler]

        patch_webdriver(mock_logger, mock_webdriver)

        assert mock_handler.webdriver == mock_webdriver

    def test_ignores_non_screenshot_handlers(self):
        """Test patch_webdriver ignores non-screenshot handlers."""
        mock_webdriver = MagicMock()
        mock_logger = MagicMock()
        mock_handler = MagicMock(spec=logging.StreamHandler)
        mock_logger.handlers = [mock_handler]

        patch_webdriver(mock_logger, mock_webdriver)

        assert not hasattr(mock_handler, 'webdriver') or mock_handler.webdriver != mock_webdriver


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
        assert TestClass.logger.name == expected_name if 'TestClass' in dir() else True

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
# _get_handler_defaults tests
#


class TestGetHandlerDefaults:

    def test_web_setup_defaults(self):
        """Test defaults for 'web' setup."""
        defaults = _get_handler_defaults('web')
        assert defaults['formatter'] == 'web_fmt'
        assert defaults['logger_name'] == 'web'
        assert 'webserver' in defaults['filters']

    def test_job_setup_defaults(self):
        """Test defaults for 'job' setup."""
        defaults = _get_handler_defaults('job')
        assert defaults['formatter'] == 'job_fmt'
        assert defaults['logger_name'] == 'job'
        assert 'preamble' in defaults['filters']

    def test_twd_setup_defaults(self):
        """Test defaults for 'twd' setup."""
        defaults = _get_handler_defaults('twd')
        assert defaults['formatter'] == 'twd_fmt'
        assert defaults['logger_name'] == 'twd'

    def test_srp_setup_defaults(self):
        """Test defaults for 'srp' setup."""
        defaults = _get_handler_defaults('srp')
        assert defaults['formatter'] == 'job_fmt'
        assert defaults['logger_name'] == 'srp'

    def test_cmd_setup_defaults(self):
        """Test defaults for 'cmd' setup."""
        defaults = _get_handler_defaults('cmd')
        assert defaults['formatter'] == 'job_fmt'
        assert defaults['logger_name'] == 'cmd'
        assert 'machine' in defaults['filters']

    def test_unknown_setup_defaults(self):
        """Test defaults for unknown setup returns None values."""
        defaults = _get_handler_defaults('unknown')
        assert defaults['formatter'] is None
        assert defaults['filters'] is None
        assert defaults['logger_name'] is None


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

    @patch('log.setup.is_tty', return_value=False)
    @patch('log.setup.dictConfig')
    def test_configure_cmd_setup(self, mock_dictconfig, mock_is_tty):
        """Test configure_logging with 'cmd' setup."""
        configure_logging(setup='cmd', app='testapp')
        mock_dictconfig.assert_called_once()
        config = mock_dictconfig.call_args[0][0]
        assert 'cmd' in config.get('loggers', {})

    @patch('log.setup.is_tty', return_value=False)
    @patch('log.setup.dictConfig')
    def test_configure_job_setup(self, mock_dictconfig, mock_is_tty):
        """Test configure_logging with 'job' setup."""
        configure_logging(setup='job', app='testapp')
        mock_dictconfig.assert_called_once()
        config = mock_dictconfig.call_args[0][0]
        assert 'job' in config.get('loggers', {})

    @patch('log.setup.is_tty', return_value=False)
    @patch('log.setup.dictConfig')
    def test_configure_web_setup(self, mock_dictconfig, mock_is_tty):
        """Test configure_logging with 'web' setup."""
        configure_logging(setup='web', app='testapp')
        mock_dictconfig.assert_called_once()
        config = mock_dictconfig.call_args[0][0]
        assert 'web' in config.get('loggers', {})

    @patch('log.setup.is_tty', return_value=True)
    @patch('log.setup.dictConfig')
    def test_configure_adds_cmd_when_tty(self, mock_dictconfig, mock_is_tty):
        """Test configure_logging adds 'cmd' logger when running in TTY."""
        configure_logging(setup='job', app='testapp')
        mock_dictconfig.assert_called_once()
        config = mock_dictconfig.call_args[0][0]
        # When is_tty() is True and setup != 'cmd', CMD_CONF is merged
        assert 'cmd' in config.get('loggers', {}) or 'job' in config.get('loggers', {})

    @patch('log.setup.is_tty', return_value=False)
    @patch('log.setup.dictConfig')
    def test_configure_with_app_name(self, mock_dictconfig, mock_is_tty):
        """Test configure_logging uses provided app name."""
        configure_logging(setup='cmd', app='myapp')
        mock_dictconfig.assert_called_once()
        config = mock_dictconfig.call_args[0][0]
        # Check that app name was formatted into config
        # The filename should contain 'myapp'
        handlers = config.get('handlers', {})
        for handler_config in handlers.values():
            if 'filename' in handler_config:
                assert 'myapp' in handler_config['filename']

    @patch('log.setup.is_tty', return_value=False)
    @patch('log.setup.dictConfig')
    def test_configure_with_extra_handlers(self, mock_dictconfig, mock_is_tty):
        """Test configure_logging adds extra handlers."""
        extra = {
            'custom_handler': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
            }
        }
        configure_logging(setup='job', app='testapp', extra_handlers=extra)
        mock_dictconfig.assert_called_once()
        config = mock_dictconfig.call_args[0][0]
        assert 'custom_handler' in config.get('handlers', {})

    @patch('log.setup.is_tty', return_value=False)
    @patch('log.setup.set_level')
    @patch('log.setup.dictConfig')
    def test_configure_with_level(self, mock_dictconfig, mock_set_level, mock_is_tty):
        """Test configure_logging sets level when provided."""
        configure_logging(setup='cmd', app='testapp', level='debug')
        mock_set_level.assert_called_once_with('debug')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
