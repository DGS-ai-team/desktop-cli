"""Text sanitization for JSON / UTF-8 safety."""

from __future__ import annotations

from typing import Any


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")
