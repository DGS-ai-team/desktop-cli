"""Tests for window health helpers."""

from desktop_cli.health import is_hung_app_window


def test_is_hung_invalid_handle():
    assert is_hung_app_window(0) is False
