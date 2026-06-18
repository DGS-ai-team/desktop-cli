"""Tests for compact JSON helpers."""

from desktop_cli.compact import (
    compact_health,
    compact_snapshot,
    compact_wait,
    compact_windows,
    is_redundant_element,
    short_type,
)


def test_short_type():
    assert short_type("EditControl") == "Edit"
    assert short_type("UnknownWidgetControl") == "Unknow"


def test_compact_windows():
    data = compact_windows([{"name": "A", "handle": 1}])
    assert data == {"w": [["A", 1]]}


def test_compact_snapshot():
    data = compact_snapshot(
        {
            "snapshot_id": "snap-abc",
            "window": {"name": "N", "handle": 2},
            "count": 1,
            "elements": [
                {
                    "ref": "e1",
                    "control_type": "ButtonControl",
                    "name": "OK",
                    "automation_id": "",
                }
            ],
        }
    )
    assert data["sid"] == "snap-abc"
    assert data["els"] == [["e1", "Btn", "OK"]]


def test_compact_health():
    data = compact_health(
        {
            "responsive": True,
            "exists": True,
            "hung": False,
            "slow": False,
            "probe_ms": 10,
            "handle": 99,
            "name": "X",
        }
    )
    assert data["ok"] is True
    assert data["ms"] == 10


def test_compact_wait_found():
    data = compact_wait(
        {
            "mode": "text",
            "text": "保存",
            "attempts": 1,
            "elapsed_ms": 100,
            "match": {"name": "保存", "control_type": "MenuItemControl"},
        }
    )
    assert data["found"] is True
    assert data["text"] == "保存"


def test_compact_wait_timeout():
    data = compact_wait(
        {
            "mode": "text",
            "text": "missing",
            "found": False,
            "attempts": 4,
            "timeout": 10.0,
        }
    )
    assert data["found"] is False
    assert data["n"] == 4


def test_is_redundant_element_menu_duplicate():
    existing = [{"name": "文件", "control_type": "MenuItemControl", "automation_id": "File"}]
    dup = {"name": "文件", "control_type": "ButtonControl", "automation_id": "ContentButton"}
    assert is_redundant_element(dup, existing) is True
