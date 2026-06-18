"""Compact response shapes to reduce agent token usage."""

from __future__ import annotations

from typing import Any

# control_type → short code
TYPE_SHORT: dict[str, str] = {
    "WindowControl": "Win",
    "DocumentControl": "Doc",
    "EditControl": "Edit",
    "ButtonControl": "Btn",
    "MenuItemControl": "Menu",
    "MenuBarControl": "Bar",
    "TabItemControl": "Tab",
    "ComboBoxControl": "Combo",
    "CheckBoxControl": "Chk",
    "RadioButtonControl": "Radio",
    "ListItemControl": "Item",
    "TreeItemControl": "Tree",
    "HyperlinkControl": "Link",
    "SplitButtonControl": "Split",
    "SliderControl": "Slider",
    "SpinnerControl": "Spin",
    "GroupControl": "Grp",
    "TextControl": "Txt",
}


def short_type(control_type: str) -> str:
    return TYPE_SHORT.get(control_type, control_type.replace("Control", "")[:6])


def compact_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    """[[title, handle], ...]"""
    return {
        "w": [[w.get("name", ""), w.get("handle", 0)] for w in windows],
    }


def compact_element(el: dict[str, Any]) -> list[Any]:
    """
    Compact element tuple:
      [ref, type, name]
      [ref, type, name, automation_id]  — when id helps disambiguation
    """
    ref = el.get("ref", "")
    name = el.get("name", "")
    ctype = short_type(el.get("control_type", ""))
    aid = el.get("automation_id") or ""
    if aid and aid not in (name, ""):
        return [ref, ctype, name, aid]
    return [ref, ctype, name]


def compact_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    window = data.get("window") or {}
    if isinstance(window, dict) and "name" in window:
        win_name = window.get("name", "")
        win_handle = window.get("handle", 0)
    else:
        win_name = data.get("window", "")
        win_handle = 0

    elements = data.get("elements") or []
    out: dict[str, Any] = {
        "sid": data.get("snapshot_id", ""),
        "win": win_name,
        "h": win_handle,
        "n": data.get("count", len(elements)),
        "els": [compact_element(e) for e in elements],
    }
    if data.get("truncated"):
        out["truncated"] = True
    return out


def compact_context(data: dict[str, Any]) -> dict[str, Any]:
    target = data.get("target") or {}
    out: dict[str, Any] = {
        "win": target.get("name") if target.get("bound") else None,
        "h": target.get("handle") if target.get("bound") else None,
        "sid": data.get("snapshot_id"),
        "n": data.get("ref_count", 0),
    }
    elements = data.get("elements") or []
    if elements:
        out["els"] = [compact_element(e) for e in elements]
    if data.get("last_action"):
        la = data["last_action"]
        out["last"] = la.get("method")
    return out


def compact_action_result(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"r": data.get("ref")}
    if data.get("name"):
        out["n"] = data["name"]
    if data.get("typed"):
        out["typed"] = data["typed"]
    if data.get("dry_run"):
        out["dry"] = True
    return out


def compact_health(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": data.get("responsive"),
        "exists": data.get("exists"),
        "hung": data.get("hung"),
        "slow": data.get("slow"),
        "ms": data.get("probe_ms"),
        "h": data.get("handle"),
        "win": data.get("name", ""),
    }


def compact_wait(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("found") is False:
        return {
            "found": False,
            "mode": data.get("mode"),
            "timeout": data.get("timeout"),
            "n": data.get("attempts"),
        }
    out: dict[str, Any] = {
        "found": True,
        "mode": data.get("mode"),
        "ms": data.get("elapsed_ms"),
        "n": data.get("attempts"),
    }
    if data.get("text"):
        out["text"] = data["text"]
    if data.get("ref"):
        out["r"] = data["ref"]
    match = data.get("match") or {}
    if match.get("name"):
        out["name"] = match["name"]
    if match.get("control_type"):
        out["type"] = short_type(match["control_type"])
    return out


def is_redundant_element(entry: dict[str, Any], existing: list[dict[str, Any]]) -> bool:
    """Drop duplicate menu mirror buttons and the root window row."""
    ctype = entry.get("control_type", "")
    name = entry.get("name", "")
    aid = entry.get("automation_id", "")

    # Root window row — attach response already has win/h
    if ctype == "WindowControl":
        return True

    # Menu bar chrome
    if ctype == "MenuBarControl":
        return True

    # "文件" MenuItem + "文件" ContentButton duplicate
    if ctype == "ButtonControl" and aid == "ContentButton":
        return any(e.get("name") == name and e.get("control_type") == "MenuItemControl" for e in existing)

    if ctype == "ButtonControl" and aid in ("File", "Edit", "View", "SettingsButton", "AddButton", "FREButton"):
        if any(
            e.get("name") == name and e.get("control_type") == "MenuItemControl"
            for e in existing
        ):
            return True

    return False
