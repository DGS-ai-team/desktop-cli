"""Automation target window — operate in background without stealing focus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from desktop_cli.windows import control_summary, resolve_window_control


@dataclass
class TargetWindow:
    handle: Optional[int] = None
    name: str = ""
    class_name: str = ""
    bound_at: float = 0.0

    def is_bound(self) -> bool:
        return bool(self.handle)

    def bind(self, title: Optional[str] = None, handle: Optional[int] = None) -> dict[str, Any]:
        import time

        control = resolve_window_control(title=title, handle=handle)
        summary = control_summary(control)
        self.handle = summary["handle"]
        self.name = summary["name"]
        self.class_name = summary["class_name"]
        self.bound_at = time.time()
        return {
            **summary,
            "mode": "background",
            "raised": False,
        }

    def unbind(self) -> dict[str, Any]:
        previous = self.to_dict() if self.is_bound() else None
        self.handle = None
        self.name = ""
        self.class_name = ""
        self.bound_at = 0.0
        return {"unbound": True, "previous": previous}

    def resolve_handle(self, override: Optional[int] = None) -> Optional[int]:
        if override is not None:
            return override
        return self.handle

    def to_dict(self) -> dict[str, Any]:
        if not self.is_bound():
            return {"bound": False}
        import time

        return {
            "bound": True,
            "handle": self.handle,
            "name": self.name,
            "class_name": self.class_name,
            "mode": "background",
            "bound_age_seconds": int(time.time() - self.bound_at) if self.bound_at else None,
        }
