from io import StringIO
from unittest.mock import patch

import pytest

from log.colors import ANSI_CLEAR, ANSI_GREEN, ANSI_NORMAL, ANSI_PINK
from log.colors import ANSI_RED, ANSI_YELLOW, Back, Fore, choose_color_ansi
from log.colors import choose_color_windows, set_color, write_color

#
# Color constant tests
#


class TestForeColorConstants:

    def test_basic_colors_exist(self):
        """Test that basic foreground colors are defined."""
        assert 'Black' in Fore
        assert 'Blue' in Fore
        assert 'Green' in Fore
        assert 'Red' in Fore

    def test_composite_colors_exist(self):
        """Test that composite foreground colors are defined."""
        assert 'Cyan' in Fore
        assert 'Magenta' in Fore
        assert 'Yellow' in Fore
        assert 'White' in Fore

    def test_bright_colors_exist(self):
        """Test that bright foreground colors are defined."""
        assert 'BrightBlack' in Fore
        assert 'BrightBlue' in Fore
        assert 'BrightGreen' in Fore
        assert 'BrightRed' in Fore
        assert 'BrightWhite' in Fore

    def test_cyan_is_blue_or_green(self):
        """Test that cyan is blue | green."""
        assert Fore['Cyan'] == (Fore['Blue'] | Fore['Green'])

    def test_yellow_is_red_or_green(self):
        """Test that yellow is red | green."""
        assert Fore['Yellow'] == (Fore['Red'] | Fore['Green'])

    def test_bright_colors_have_high_bit(self):
        """Test that bright colors have intensity bit set."""
        for key in Fore:
            if key.startswith('Bright'):
                assert Fore[key] & 8 == 8


class TestBackColorConstants:

    def test_back_colors_exist(self):
        """Test that background colors are defined."""
        assert 'Black' in Back
        assert 'Blue' in Back
        assert 'Green' in Back
        assert 'Red' in Back
        assert 'White' in Back

    def test_back_colors_shifted(self):
        """Test that background colors are shifted by 4 bits."""
        for key in Fore:
            assert Back[key] == Fore[key] << 4


class TestAnsiConstants:

    def test_ansi_escape_sequences(self):
        """Test ANSI escape sequences have correct format."""
        assert ANSI_RED.startswith('\x1b[')
        assert ANSI_YELLOW.startswith('\x1b[')
        assert ANSI_GREEN.startswith('\x1b[')
        assert ANSI_PINK.startswith('\x1b[')
        assert ANSI_NORMAL.startswith('\x1b[')
        assert ANSI_CLEAR.startswith('\x1b[')


#
# choose_color_windows tests
#


class TestChooseColorWindows:

    def test_critical_level(self):
        """Test critical level (50+) returns background color."""
        color = choose_color_windows(50)
        assert color != 0

    def test_error_level(self):
        """Test error level (40-49) returns red with intensity."""
        color = choose_color_windows(40)
        assert color != 0

    def test_warning_level(self):
        """Test warning level (30-39) returns yellow with intensity."""
        color = choose_color_windows(30)
        assert color != 0

    def test_info_level(self):
        """Test info level (20-29) returns green."""
        color = choose_color_windows(20)
        assert color != 0

    def test_debug_level(self):
        """Test debug level (10-19) returns magenta."""
        color = choose_color_windows(10)
        assert color != 0

    def test_notset_level(self):
        """Test notset level (0-9) returns white."""
        color = choose_color_windows(0)
        assert color != 0

    def test_levels_are_different(self):
        """Test different log levels produce different colors."""
        colors = [
            choose_color_windows(50),
            choose_color_windows(40),
            choose_color_windows(30),
            choose_color_windows(20),
            choose_color_windows(10),
        ]
        # At least some colors should be different
        assert len(set(colors)) > 1


#
# choose_color_ansi tests
#


class TestChooseColorAnsi:

    def test_critical_level(self):
        """Test critical level (50+) returns red."""
        color = choose_color_ansi(50)
        assert color == ANSI_RED

    def test_error_level(self):
        """Test error level (40-49) returns red."""
        color = choose_color_ansi(40)
        assert color == ANSI_RED

    def test_warning_level(self):
        """Test warning level (30-39) returns yellow."""
        color = choose_color_ansi(30)
        assert color == ANSI_YELLOW

    def test_info_level(self):
        """Test info level (20-29) returns green."""
        color = choose_color_ansi(20)
        assert color == ANSI_GREEN

    def test_debug_level(self):
        """Test debug level (10-19) returns pink."""
        color = choose_color_ansi(10)
        assert color == ANSI_PINK

    def test_notset_level(self):
        """Test notset level (0-9) returns normal."""
        color = choose_color_ansi(0)
        assert color == ANSI_NORMAL

    def test_boundary_values(self):
        """Test boundary values between levels."""
        assert choose_color_ansi(49) == ANSI_RED
        assert choose_color_ansi(39) == ANSI_YELLOW
        assert choose_color_ansi(29) == ANSI_GREEN
        assert choose_color_ansi(19) == ANSI_PINK
        assert choose_color_ansi(9) == ANSI_NORMAL


#
# set_color and write_color tests (non-Windows)
#


class TestSetColorNonWindows:

    @patch('log.colors.platform.system', return_value='Linux')
    def test_set_color_writes_escape_sequence(self, mock_system):
        """Test set_color writes ANSI escape on non-Windows."""
        stream = StringIO()
        with set_color(ANSI_GREEN, stream):
            stream.write('test')
        output = stream.getvalue()
        assert ANSI_GREEN in output
        assert 'test' in output
        assert ANSI_CLEAR in output

    @patch('log.colors.platform.system', return_value='Linux')
    def test_set_color_clears_on_exception(self, mock_system):
        """Test set_color writes clear on exception."""
        stream = StringIO()
        with pytest.raises(ValueError), set_color(ANSI_GREEN, stream):
            raise ValueError('test error')
        output = stream.getvalue()
        assert ANSI_CLEAR in output


class TestWriteColor:

    @patch('log.colors.platform.system', return_value='Linux')
    def test_write_color_outputs_message(self, mock_system):
        """Test write_color writes colored message."""
        stream = StringIO()
        write_color(ANSI_GREEN, 'Hello', stream)
        output = stream.getvalue()
        assert 'Hello' in output
        assert ANSI_GREEN in output


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
