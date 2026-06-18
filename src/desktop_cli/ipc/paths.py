"""Runtime paths and pipe names scoped per user session."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from desktop_cli.session import get_session_info


def _sanitize(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)


def rpc_address() -> tuple[str, int]:
    """Preferred RPC address — actual port comes from daemon.json when running."""
    info = get_session_info()
    port = 45000 + (max(info["session_id"], 0) % 1000)
    return ("127.0.0.1", port)


def get_rpc_address() -> tuple[str, int]:
    info = read_daemon_info()
    if info and isinstance(info.get("address"), dict):
        addr = info["address"]
        host = addr.get("host", "127.0.0.1")
        port = addr.get("port")
        if port is not None:
            return (host, int(port))
    return rpc_address()


def authkey() -> bytes:
    info = get_session_info()
    raw = f"desktop-cli|{info['username']}|{info['session_id']}".encode("utf-8")
    return hashlib.sha256(raw).digest()


def mutex_name() -> str:
    info = get_session_info()
    user = _sanitize(info["username"])
    return f"Local\\desktop-cli-daemon-{info['session_id']}-{user}"


def runtime_dir() -> Path:
    info = get_session_info()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = base / "desktop-cli" / f"session-{info['session_id']}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def daemon_info_path() -> Path:
    return runtime_dir() / "daemon.json"


def read_daemon_info() -> dict[str, Any] | None:
    path = daemon_info_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_daemon_info(info: dict[str, Any]) -> None:
    daemon_info_path().write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_daemon_info() -> None:
    path = daemon_info_path()
    if path.exists():
        path.unlink()
