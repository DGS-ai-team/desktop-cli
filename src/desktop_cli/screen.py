"""Screen capture."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any, Optional

import pyautogui


def capture_screen(
    output_path: Optional[str] = None,
    as_base64: bool = False,
) -> dict[str, Any]:
    image = pyautogui.screenshot()
    width, height = image.size
    result: dict[str, Any] = {"width": width, "height": height}

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(path))
        result["path"] = str(path.resolve())

    if as_base64:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        result["base64"] = base64.b64encode(buffer.getvalue()).decode("ascii")

    if not output_path and not as_base64:
        # Default: return base64 when no file path given.
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        result["base64"] = base64.b64encode(buffer.getvalue()).decode("ascii")

    return result
