"""Keyboard and mouse input via pyautogui."""

from __future__ import annotations

from typing import Any

import pyautogui

# Fail fast when the mouse hits a screen corner.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def type_text(text: str, interval: float = 0.02) -> dict[str, Any]:
    pyautogui.write(text, interval=interval)
    return {"text": text, "length": len(text)}


def press_hotkey(*keys: str) -> dict[str, Any]:
    pyautogui.hotkey(*keys)
    return {"keys": list(keys)}


def press_key(key: str) -> dict[str, Any]:
    pyautogui.press(key)
    return {"key": key}


def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> dict[str, Any]:
    pyautogui.click(x=x, y=y, button=button, clicks=clicks)
    return {"x": x, "y": y, "button": button, "clicks": clicks}


def mouse_move(x: int, y: int) -> dict[str, Any]:
    pyautogui.moveTo(x, y)
    return {"x": x, "y": y}
