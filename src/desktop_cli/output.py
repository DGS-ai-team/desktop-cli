"""Unified output — text (default, agent-browser style) or JSON."""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Literal, Optional

OutputFormat = Literal["text", "json", "json-full"]

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_TIMEOUT = 2
EXIT_SESSION = 3
EXIT_ERROR = 4
EXIT_LEASE = 5


class CLIError(Exception):
    """Expected CLI failure with a specific exit code."""

    def __init__(
        self,
        message: str,
        exit_code: int = EXIT_ERROR,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.data = data


def success(
    command: str,
    data: Any = None,
    *,
    fmt: OutputFormat = "text",
    text: Optional[str] = None,
    pretty: bool = False,
    duration_ms: Optional[int] = None,
) -> None:
    if fmt == "text":
        _emit_text(text if text is not None else "OK", EXIT_OK)
    else:
        compact = fmt == "json"
        _emit_json(True, command, data, None, EXIT_OK, pretty, compact, duration_ms)


def failure(
    command: str,
    error: str,
    *,
    exit_code: int = EXIT_ERROR,
    data: Any = None,
    fmt: OutputFormat = "text",
    pretty: bool = False,
    duration_ms: Optional[int] = None,
) -> None:
    if fmt == "text":
        msg = error
        if data and isinstance(data, dict) and data.get("ref"):
            from desktop_cli.format import display_ref

            msg = f"{error} (ref {display_ref(str(data['ref']))})"
        _emit_text(f"错误: {msg}", exit_code, stream=sys.stderr)
    else:
        compact = fmt == "json"
        _emit_json(False, command, data, error, exit_code, pretty, compact, duration_ms)


def _emit_text(text: str, exit_code: int, stream=None) -> None:
    stream = stream or sys.stdout
    stream.buffer.write(text.encode("utf-8", errors="replace"))
    stream.buffer.write(b"\n")
    stream.buffer.flush()
    raise SystemExit(exit_code)


def _emit_json(
    ok: bool,
    command: str,
    data: Any,
    error: Optional[str],
    exit_code: int,
    pretty: bool,
    compact: bool,
    duration_ms: Optional[int],
) -> None:
    payload: dict[str, Any] = {
        "ok": ok,
        "command": command,
        "data": data,
        "error": error,
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms

    indent = 2 if pretty else None
    separators = (",", ":") if compact and not pretty else (", ", ": ")
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=indent,
        separators=separators,
        default=str,
    )
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()
    raise SystemExit(exit_code)


class timed:
    """Context manager that records elapsed milliseconds."""

    def __init__(self) -> None:
        self.start = 0.0
        self.duration_ms = 0

    def __enter__(self) -> timed:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.duration_ms = int((time.perf_counter() - self.start) * 1000)
