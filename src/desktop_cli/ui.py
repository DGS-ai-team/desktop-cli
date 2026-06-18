"""UI Automation tree dump, find, and click."""

from __future__ import annotations

import time
from typing import Any, Optional

import uiautomation as auto

from desktop_cli.windows import control_summary


def dump_tree(
    depth: int = 3,
    handle: Optional[int] = None,
    max_children: int = 50,
) -> dict[str, Any]:
    if handle is not None:
        root = auto.ControlFromHandle(handle)
        if not root.Exists(maxSearchSeconds=1):
            from desktop_cli.output import CLIError, EXIT_NOT_FOUND

            raise CLIError(f"No window with handle {handle}", EXIT_NOT_FOUND)
    else:
        root = auto.GetForegroundControl()

    return _serialize_control(root, current_depth=0, max_depth=depth, max_children=max_children)


def find_controls(
    name: Optional[str] = None,
    automation_id: Optional[str] = None,
    control_type: Optional[str] = None,
    timeout: float = 5.0,
    root_handle: Optional[int] = None,
) -> list[dict[str, Any]]:
    _require_selector(name, automation_id)
    matches = _search_controls(
        _search_root(root_handle),
        name=name,
        automation_id=automation_id,
        control_type=control_type,
        timeout=timeout,
    )
    return [control_summary(m) for m in matches]


def click_control(
    name: Optional[str] = None,
    automation_id: Optional[str] = None,
    control_type: Optional[str] = None,
    timeout: float = 5.0,
    root_handle: Optional[int] = None,
    dry_run: bool = False,
    background: bool = True,
) -> dict[str, Any]:
    _require_selector(name, automation_id)

    matches = _search_controls(
        _search_root(root_handle),
        name=name,
        automation_id=automation_id,
        control_type=control_type,
        timeout=timeout,
    )

    if not matches:
        from desktop_cli.output import CLIError, EXIT_NOT_FOUND

        raise CLIError(_not_found_message(name, automation_id), EXIT_NOT_FOUND)

    if len(matches) > 1:
        from desktop_cli.output import CLIError, EXIT_ERROR

        raise CLIError(
            f"Ambiguous match: {len(matches)} controls found",
            EXIT_ERROR,
            data={"candidates": [control_summary(m) for m in matches[:10]]},
        )

    target = matches[0]
    summary = control_summary(target)

    if dry_run:
        summary["dry_run"] = True
        summary["background"] = background
        return summary

    _activate_control(target, background=background)
    summary["background"] = background
    return summary


def wait_for_control(
    name: Optional[str] = None,
    automation_id: Optional[str] = None,
    control_type: Optional[str] = None,
    timeout: float = 10.0,
    root_handle: Optional[int] = None,
) -> dict[str, Any]:
    _require_selector(name, automation_id)

    end = time.monotonic() + timeout
    root = _search_root(root_handle)
    while time.monotonic() < end:
        matches = _walk_find(root, name, automation_id, control_type)
        if matches:
            return control_summary(matches[0])
        time.sleep(0.2)

    from desktop_cli.output import CLIError, EXIT_TIMEOUT

    raise CLIError(
        f"Timed out after {timeout}s waiting for control",
        EXIT_TIMEOUT,
    )


def _require_selector(name: Optional[str], automation_id: Optional[str]) -> None:
    from desktop_cli.output import CLIError, EXIT_ERROR

    if not name and not automation_id:
        raise CLIError("Provide --name and/or --automation-id", EXIT_ERROR)


def _not_found_message(name: Optional[str], automation_id: Optional[str]) -> str:
    parts = []
    if name:
        parts.append(f"name={name!r}")
    if automation_id:
        parts.append(f"automation_id={automation_id!r}")
    return "Control not found: " + ", ".join(parts)


def _search_root(handle: Optional[int]) -> auto.Control:
    if handle is not None:
        ctrl = auto.ControlFromHandle(handle)
        if ctrl.Exists(maxSearchSeconds=1):
            return ctrl
        from desktop_cli.output import CLIError, EXIT_NOT_FOUND

        raise CLIError(f"No window with handle {handle}", EXIT_NOT_FOUND)
    return auto.GetRootControl()


def _search_controls(
    root: auto.Control,
    name: Optional[str],
    automation_id: Optional[str],
    control_type: Optional[str],
    timeout: float,
) -> list[auto.Control]:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        matches = _walk_find(root, name, automation_id, control_type)
        if matches:
            return matches
        time.sleep(0.3)
    return []


def _walk_find(
    root: auto.Control,
    name: Optional[str],
    automation_id: Optional[str],
    control_type: Optional[str],
) -> list[auto.Control]:
    matches: list[auto.Control] = []
    ct = _resolve_control_type(control_type)

    for control, _depth in auto.WalkControl(root, includeTop=False, maxDepth=0xFFFFFFFF):
        if name and name not in (control.Name or ""):
            continue
        if automation_id and control.AutomationId != automation_id:
            continue
        if ct is not None and control.ControlType != ct:
            continue
        matches.append(control)

    return matches


def _resolve_control_type(name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    normalized = name.lower().replace("control", "")
    for member in dir(auto.ControlType):
        if member.startswith("_"):
            continue
        if member.lower().replace("control", "") == normalized:
            return getattr(auto.ControlType, member)
    return None


def _activate_control(control: auto.Control, *, background: bool = True) -> None:
    try:
        pattern = control.GetInvokePattern()
        if pattern is not None:
            pattern.Invoke()
            return
    except Exception:
        pass

    control.Click(simulateMove=not background)


def _serialize_control(
    control: auto.Control,
    current_depth: int,
    max_depth: int,
    max_children: int,
) -> dict[str, Any]:
    rect = control.BoundingRectangle
    node: dict[str, Any] = {
        "name": control.Name,
        "control_type": control.ControlTypeName,
        "automation_id": control.AutomationId,
        "class_name": control.ClassName,
        "handle": control.NativeWindowHandle,
        "rect": [rect.left, rect.top, rect.right, rect.bottom],
        "enabled": control.IsEnabled,
    }

    if current_depth >= max_depth:
        return node

    children: list[dict[str, Any]] = []
    try:
        for i, child in enumerate(control.GetChildren()):
            if i >= max_children:
                node["children_truncated"] = True
                break
            children.append(
                _serialize_control(child, current_depth + 1, max_depth, max_children)
            )
    except Exception:
        node["children_error"] = True

    if children:
        node["children"] = children

    return node
