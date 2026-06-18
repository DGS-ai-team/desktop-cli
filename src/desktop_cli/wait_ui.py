"""Poll bound window until UI text or ref is ready."""

from __future__ import annotations

import time
from typing import Any, Optional

import uiautomation as auto

from desktop_cli.format import normalize_ref
from desktop_cli.refs import RefError, RefRegistry
from desktop_cli.util import safe_text
from desktop_cli.windows import control_summary


def find_text_in_window(handle: int, text: str) -> Optional[dict[str, Any]]:
    try:
        root = auto.ControlFromHandle(handle)
        if not root.Exists(maxSearchSeconds=0.5):
            return None
    except Exception:
        return None

    try:
        for control, _depth in auto.WalkControl(root, includeTop=True, maxDepth=0xFFFFFFFF):
            try:
                name = safe_text(control.Name)
                if text not in name:
                    continue
                summary = control_summary(control)
                summary["matched_text"] = text
                return summary
            except Exception:
                continue
    except Exception:
        return None
    return None


def wait_for_text(
    handle: int,
    text: str,
    *,
    timeout: float = 10.0,
    interval: float = 0.5,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    attempts = 0
    last_probe_ms = 0

    while time.monotonic() < deadline:
        attempts += 1
        start = time.perf_counter()
        try:
            match = find_text_in_window(handle, text)
        except Exception:
            match = None
        last_probe_ms = int((time.perf_counter() - start) * 1000)
        if match:
            elapsed_ms = int((time.monotonic() - (deadline - timeout)) * 1000)
            return {
                "mode": "text",
                "text": text,
                "match": match,
                "attempts": attempts,
                "probe_ms": last_probe_ms,
                "elapsed_ms": elapsed_ms,
            }
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))

    return {
        "mode": "text",
        "text": text,
        "found": False,
        "attempts": attempts,
        "last_probe_ms": last_probe_ms,
        "timeout": timeout,
    }


def wait_for_ref(
    registry: RefRegistry,
    handle: int,
    ref: str,
    *,
    timeout: float = 10.0,
    interval: float = 0.5,
) -> dict[str, Any]:
    ref = normalize_ref(ref)
    deadline = time.monotonic() + timeout
    attempts = 0
    last_error: Optional[str] = None

    while time.monotonic() < deadline:
        attempts += 1
        try:
            control = registry.resolve(ref)
            summary = control_summary(control)
            summary["ref"] = ref
            elapsed_ms = int((time.monotonic() - (deadline - timeout)) * 1000)
            return {
                "mode": "ref",
                "ref": ref,
                "match": summary,
                "attempts": attempts,
                "elapsed_ms": elapsed_ms,
            }
        except RefError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))

    return {
        "mode": "ref",
        "ref": ref,
        "found": False,
        "attempts": attempts,
        "last_error": last_error,
        "timeout": timeout,
    }
