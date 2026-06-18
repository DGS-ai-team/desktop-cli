"""Window health — detect hung / unresponsive UI."""

from __future__ import annotations

import ctypes
import time
from typing import Any

import uiautomation as auto

from desktop_cli.util import safe_text


def is_hung_app_window(handle: int) -> bool:
    if not handle:
        return False
    return bool(ctypes.windll.user32.IsHungAppWindow(handle))


def check_window_health(handle: int) -> dict[str, Any]:
    ctrl = auto.ControlFromHandle(handle)
    start = time.perf_counter()
    try:
        exists = ctrl.Exists(maxSearchSeconds=1)
    except Exception:
        exists = False
    probe_ms = int((time.perf_counter() - start) * 1000)
    hung = is_hung_app_window(handle) if exists else False
    slow = probe_ms >= 3000
    name = ""
    if exists:
        try:
            name = safe_text(ctrl.Name)
        except Exception:
            name = ""
    return {
        "exists": exists,
        "hung": hung,
        "slow": slow,
        "responsive": exists and not hung and not slow,
        "probe_ms": probe_ms,
        "handle": handle,
        "name": name,
    }
