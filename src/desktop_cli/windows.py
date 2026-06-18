"""Window enumeration — background only, no focus stealing."""

from __future__ import annotations

from typing import Any, Optional

import uiautomation as auto

from desktop_cli.util import safe_text


def list_windows(visible_only: bool = True) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    root = auto.GetRootControl()
    for child in root.GetChildren():
        if child.ControlType != auto.ControlType.WindowControl:
            continue
        handle = child.NativeWindowHandle
        if visible_only and not handle:
            continue
        name = child.Name or ""
        if visible_only and not name:
            continue
        rect = child.BoundingRectangle
        results.append(
            {
                "name": safe_text(name),
                "class_name": safe_text(child.ClassName),
                "handle": handle,
                "rect": _rect_to_list(rect),
                "enabled": child.IsEnabled,
            }
        )
    return results


def resolve_window_control(
    title: Optional[str] = None,
    handle: Optional[int] = None,
) -> auto.Control:
    from desktop_cli.output import CLIError, EXIT_NOT_FOUND

    if handle is not None:
        ctrl = auto.ControlFromHandle(handle)
        if ctrl.Exists(maxSearchSeconds=1):
            return ctrl
        raise CLIError(f"No window with handle {handle}", EXIT_NOT_FOUND)

    if not title:
        raise CLIError("Provide --title or --handle", EXIT_NOT_FOUND)

    win = auto.WindowControl(searchDepth=1, SubName=title)
    if win.Exists(maxSearchSeconds=3):
        return win

    raise CLIError(f"No window matching title: {title!r}", EXIT_NOT_FOUND)


def control_summary(control: auto.Control) -> dict[str, Any]:
    rect = control.BoundingRectangle
    return {
        "name": safe_text(control.Name),
        "class_name": safe_text(control.ClassName),
        "automation_id": safe_text(control.AutomationId),
        "control_type": safe_text(control.ControlTypeName),
        "handle": control.NativeWindowHandle,
        "rect": _rect_to_list(rect),
    }


def _rect_to_list(rect: Any) -> list[int]:
    return [rect.left, rect.top, rect.right, rect.bottom]
