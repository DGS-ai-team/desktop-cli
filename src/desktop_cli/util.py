"""Text sanitization for JSON / UTF-8 safety."""

from __future__ import annotations

import os
import sys
from typing import Any


def ensure_utf8_stdio() -> None:
    """Avoid UnicodeEncodeError when Typer/Rich prints Chinese help on Windows."""
    if sys.platform != "win32":
        return
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")
