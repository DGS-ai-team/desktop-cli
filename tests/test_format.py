"""Tests for ref normalization and text formatting."""

from desktop_cli.format import (
    display_ref,
    format_health_text,
    format_response,
    format_wait_text,
    normalize_ref,
)


def test_normalize_ref_variants():
    assert normalize_ref("@e3") == "e3"
    assert normalize_ref("e3") == "e3"
    assert normalize_ref("3") == "e3"
    assert normalize_ref("  @12  ") == "e12"


def test_display_ref():
    assert display_ref("e5") == "@e5"
    assert display_ref("@e5") == "@e5"


def test_format_response_snapshot():
    text = format_response(
        "open",
        {
            "window": {"name": "Notepad", "handle": 123},
            "elements": [
                {"ref": "e1", "control_type": "EditControl", "name": "editor"},
            ],
        },
    )
    assert "窗口: Notepad" in text
    assert "@e1 [Edit]" in text
    assert '"editor"' in text


def test_format_response_click():
    text = format_response("click", {"ref": "e2", "name": "文件"})
    assert text == '已点击 @e2 "文件"'


def test_format_health_text():
    text = format_health_text(
        {
            "exists": True,
            "hung": False,
            "slow": False,
            "responsive": True,
            "probe_ms": 42,
            "handle": 100,
            "name": "Notepad",
        }
    )
    assert "状态: 正常" in text
    assert "探测耗时: 42ms" in text


def test_format_wait_text():
    text = format_wait_text(
        {
            "mode": "text",
            "text": "新建",
            "attempts": 2,
            "elapsed_ms": 1200,
            "match": {"name": "新建", "control_type": "MenuItemControl"},
        }
    )
    assert "已找到" in text
    assert "新建" in text
    assert "1.2s" in text
