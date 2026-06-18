"""Session detection — critical for Windows Server agent deployments."""

from __future__ import annotations

import ctypes
import getpass
import os
import sys
from typing import Any

if sys.platform != "win32":
    raise RuntimeError("desktop-cli only supports Windows")


def get_session_info() -> dict[str, Any]:
    session_id = _current_session_id()
    session_name = os.environ.get("SESSIONNAME", "")
    username = getpass.getuser()

    # Session 0 is the non-interactive service session (Vista+).
    interactive = session_id != 0

    warnings: list[str] = []
    if not interactive:
        warnings.append(
            "Running in Session 0 — desktop automation will not work. "
            "Run in an interactive RDP or console user session."
        )
    if session_name.upper() == "SERVICES":
        warnings.append("SESSIONNAME is Services — not an interactive desktop session.")

    return {
        "username": username,
        "session_id": session_id,
        "session_name": session_name,
        "interactive": interactive,
        "computer_name": os.environ.get("COMPUTERNAME", ""),
        "warnings": warnings,
    }


def ensure_interactive() -> None:
    info = get_session_info()
    if not info["interactive"]:
        from desktop_cli.output import CLIError, EXIT_SESSION

        raise CLIError(
            "Not running in an interactive session (Session 0). "
            "Start desktop-cli in a logged-in RDP or console session.",
            EXIT_SESSION,
        )


def _current_session_id() -> int:
    kernel32 = ctypes.windll.kernel32
    session_id = ctypes.c_ulong()
    pid = kernel32.GetCurrentProcessId()
    if not kernel32.ProcessIdToSessionId(pid, ctypes.byref(session_id)):
        return -1
    return session_id.value
