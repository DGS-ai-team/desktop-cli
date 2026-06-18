"""Snapshot refs — compact element handles for agent workflows."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import uiautomation as auto

from desktop_cli.compact import is_redundant_element
from desktop_cli.util import safe_text
from desktop_cli.windows import control_summary

INTERACTIVE_CONTROL_TYPES = {
    auto.ControlType.ButtonControl,
    auto.ControlType.EditControl,
    auto.ControlType.ComboBoxControl,
    auto.ControlType.CheckBoxControl,
    auto.ControlType.RadioButtonControl,
    auto.ControlType.HyperlinkControl,
    auto.ControlType.ListItemControl,
    auto.ControlType.MenuItemControl,
    auto.ControlType.TabItemControl,
    auto.ControlType.TreeItemControl,
    auto.ControlType.SliderControl,
    auto.ControlType.SpinnerControl,
    auto.ControlType.SplitButtonControl,
    auto.ControlType.DocumentControl,
}


@dataclass
class RefEntry:
    ref: str
    runtime_id: list[int]
    name: str
    control_type: str
    automation_id: str
    class_name: str
    rect: list[int]
    enabled: bool
    window_handle: int
    snapshot_id: str


@dataclass
class RefRegistry:
    snapshot_id: str = ""
    created_at: float = 0.0
    window_handle: int = 0
    window_name: str = ""
    refs: dict[str, RefEntry] = field(default_factory=dict)

    def clear(self) -> None:
        self.snapshot_id = ""
        self.created_at = 0.0
        self.window_handle = 0
        self.window_name = ""
        self.refs.clear()

    def build_snapshot(
        self,
        handle: Optional[int] = None,
        max_elements: int = 200,
    ) -> dict[str, Any]:
        root = _resolve_root(handle)
        self.clear()
        self.snapshot_id = f"snap-{secrets.token_hex(4)}"
        self.created_at = time.time()
        self.window_handle = root.NativeWindowHandle
        self.window_name = safe_text(root.Name)

        elements: list[dict[str, Any]] = []
        count = 0
        truncated = False

        for control, _depth in auto.WalkControl(root, includeTop=True, maxDepth=0xFFFFFFFF):
            try:
                if not _is_interactive(control):
                    continue
                rect = control.BoundingRectangle
                row_preview = {
                    "name": safe_text(control.Name),
                    "control_type": safe_text(control.ControlTypeName),
                    "automation_id": safe_text(control.AutomationId),
                }
                if is_redundant_element(row_preview, elements):
                    continue
                if count >= max_elements:
                    truncated = True
                    break
                count += 1
                ref_id = f"e{count}"
                entry = RefEntry(
                    ref=ref_id,
                    runtime_id=_runtime_id_list(control),
                    name=row_preview["name"],
                    control_type=row_preview["control_type"],
                    automation_id=row_preview["automation_id"],
                    class_name=safe_text(control.ClassName),
                    rect=[rect.left, rect.top, rect.right, rect.bottom],
                    enabled=control.IsEnabled,
                    window_handle=self.window_handle,
                    snapshot_id=self.snapshot_id,
                )
                row = _entry_to_dict(entry)
                self.refs[ref_id] = entry
                elements.append(row)
            except Exception:
                continue

        return {
            "snapshot_id": self.snapshot_id,
            "window": {
                "name": self.window_name,
                "handle": self.window_handle,
            },
            "count": len(elements),
            "truncated": truncated,
            "elements": elements,
        }

    def resolve(self, ref: str) -> auto.Control:
        entry = self.refs.get(ref)
        if not entry:
            raise RefError(f"Unknown ref {ref!r}. Run snapshot first.", code="REF_UNKNOWN")

        root = _resolve_root(entry.window_handle or None)
        target = _find_by_runtime_id(root, entry.runtime_id)
        if target is None:
            target = _find_by_locator(root, entry)
        if target is None:
            raise RefError(
                f"Ref {ref!r} could not be resolved. Run snapshot again.",
                code="REF_STALE",
                data=_entry_to_dict(entry),
            )
        return target

    def get_context(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_age_seconds": int(time.time() - self.created_at) if self.created_at else None,
            "window": {
                "name": self.window_name,
                "handle": self.window_handle,
            },
            "ref_count": len(self.refs),
            "refs": [_entry_to_dict(e) for e in self.refs.values()],
        }


class RefError(Exception):
    def __init__(self, message: str, *, code: str = "REF_ERROR", data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


def _resolve_root(handle: Optional[int]) -> auto.Control:
    if handle is not None:
        ctrl = auto.ControlFromHandle(handle)
        if ctrl.Exists(maxSearchSeconds=1):
            return ctrl
        raise RefError(f"No window with handle {handle}", code="NOT_FOUND")
    return auto.GetForegroundControl()


def _is_interactive(control: auto.Control) -> bool:
    if not control.IsEnabled:
        return False
    rect = control.BoundingRectangle
    if rect.right <= rect.left or rect.bottom <= rect.top:
        return False
    if control.ControlType in INTERACTIVE_CONTROL_TYPES:
        return True
    name = control.Name or ""
    if name and control.ControlTypeName in ("TextControl", "GroupControl"):
        return False
    return bool(name)


def _runtime_id_list(control: auto.Control) -> list[int]:
    try:
        rid = control.RuntimeId
        if rid:
            return list(rid)
    except Exception:
        pass
    return []


def _find_by_runtime_id(root: auto.Control, runtime_id: list[int]) -> Optional[auto.Control]:
    if not runtime_id:
        return None
    target = tuple(runtime_id)
    for control, _depth in auto.WalkControl(root, includeTop=True, maxDepth=0xFFFFFFFF):
        try:
            rid = control.RuntimeId
            if rid and tuple(rid) == target:
                return control
        except Exception:
            continue
    return None


def _find_by_locator(root: auto.Control, entry: RefEntry) -> Optional[auto.Control]:
    """Fallback when RuntimeId is missing (common for Win32 menus)."""
    if entry.name and entry.control_type == "MenuItemControl":
        item = root.MenuItemControl(Name=entry.name)
        if item.Exists(maxSearchSeconds=0.5):
            return item

    ct = _control_type_from_name(entry.control_type)
    candidates: list[auto.Control] = []

    for control, _depth in auto.WalkControl(root, includeTop=True, maxDepth=0xFFFFFFFF):
        try:
            if entry.name and safe_text(control.Name) != entry.name:
                continue
            if entry.automation_id and safe_text(control.AutomationId) != entry.automation_id:
                continue
            if ct is not None and control.ControlType != ct:
                continue
            if entry.class_name and safe_text(control.ClassName) != entry.class_name:
                continue
            candidates.append(control)
        except Exception:
            continue

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return _best_rect_match(candidates, entry.rect)


def _control_type_from_name(type_name: str) -> Optional[int]:
    if not type_name:
        return None
    for member in dir(auto.ControlType):
        if member.startswith("_"):
            continue
        if member == type_name or member.lower() == type_name.lower():
            return getattr(auto.ControlType, member)
    return None


def _best_rect_match(candidates: list[auto.Control], target_rect: list[int]) -> Optional[auto.Control]:
    if not target_rect or target_rect == [0, 0, 0, 0]:
        return None

    def distance(control: auto.Control) -> int:
        rect = control.BoundingRectangle
        current = [rect.left, rect.top, rect.right, rect.bottom]
        return _rect_center_distance(current, target_rect)

    ranked = sorted(candidates, key=distance)
    if ranked and distance(ranked[0]) <= 80:
        return ranked[0]
    return None


def _rect_center_distance(a: list[int], b: list[int]) -> int:
    ax = (a[0] + a[2]) // 2
    ay = (a[1] + a[3]) // 2
    bx = (b[0] + b[2]) // 2
    by = (b[1] + b[3]) // 2
    return abs(ax - bx) + abs(by - by)


def _entry_to_dict(entry: RefEntry) -> dict[str, Any]:
    return {
        "ref": entry.ref,
        "name": entry.name,
        "control_type": entry.control_type,
        "automation_id": entry.automation_id,
        "rect": entry.rect,
        "enabled": entry.enabled,
        "has_runtime_id": bool(entry.runtime_id),
    }


def click_ref(
    registry: RefRegistry,
    ref: str,
    *,
    dry_run: bool = False,
    background: bool = True,
) -> dict[str, Any]:
    control = registry.resolve(ref)
    summary = control_summary(control)
    summary["ref"] = ref
    summary["background"] = background
    if dry_run:
        summary["dry_run"] = True
        return summary
    _activate_control(control, background=background)
    return summary


def type_ref(registry: RefRegistry, ref: str, text: str, *, clear: bool = False) -> dict[str, Any]:
    control = registry.resolve(ref)
    summary = control_summary(control)
    summary["ref"] = ref
    if clear:
        control.SendKeys("{Ctrl}a{Delete}")
    control.SendKeys(text)
    summary["typed"] = text
    return summary


def _activate_control(control: auto.Control, *, background: bool = True) -> None:
    try:
        pattern = control.GetInvokePattern()
        if pattern is not None:
            pattern.Invoke()
            return
    except Exception:
        pass

    if background:
        control.Click(simulateMove=False)
    else:
        control.Click(simulateMove=True)
