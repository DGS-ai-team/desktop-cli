"""IPC client — ping, RPC call, implicit daemon bootstrap."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from multiprocessing.connection import Client
from typing import Any, Optional

from desktop_cli import __version__
from desktop_cli.ipc.paths import (
    authkey,
    get_rpc_address,
    read_daemon_info,
    remove_daemon_info,
    rpc_address,
    write_daemon_info,
)
from desktop_cli.ipc.protocol import decode_message, encode_message, make_request

PING_TIMEOUT = 0.5
STARTUP_TIMEOUT = 8.0
RPC_TIMEOUT = 60.0

ERROR_ALREADY_EXISTS = 183


def ping(timeout: float = PING_TIMEOUT) -> bool:
    try:
        result = _call_once("daemon.ping", {}, timeout=timeout)
        return bool(result.get("ok"))
    except Exception:
        return False


def call(method: str, params: Optional[dict[str, Any]] = None, timeout: float = RPC_TIMEOUT) -> dict[str, Any]:
    ensure_daemon()
    return _call_once(method, params or {}, timeout=timeout)


def ensure_daemon() -> None:
    if ping():
        return

    info = read_daemon_info()
    if info and info.get("pid"):
        _terminate_pid(info.get("pid"))
        remove_daemon_info()

    with _startup_mutex():
        if ping():
            return
        _start_daemon_process()
        _wait_until_ready()


def stop_daemon() -> bool:
    info = read_daemon_info()
    if info and ping(timeout=0.3):
        try:
            _call_once("daemon.shutdown", {}, timeout=2.0)
        except Exception:
            pass
    if info:
        _terminate_pid(info.get("pid"))
    remove_daemon_info()
    return True


def daemon_status() -> dict[str, Any]:
    info = read_daemon_info()
    alive = ping(timeout=0.3)
    status: dict[str, Any] = {
        "running": alive,
        "address": {"host": get_rpc_address()[0], "port": get_rpc_address()[1]},
        "version": __version__,
        "pid": info.get("pid") if info else None,
    }
    if alive:
        try:
            resp = _call_once("daemon.ping", {}, timeout=1.0)
            status["daemon"] = resp.get("data")
        except Exception as exc:
            status["daemon_error"] = str(exc)
    return status


def _call_once(method: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = make_request(method, params)
    conn = Client(get_rpc_address(), authkey=authkey())
    try:
        conn.send_bytes(encode_message(request))
        if not conn.poll(timeout):
            raise TimeoutError(f"RPC timeout after {timeout}s for {method}")
        raw = conn.recv_bytes()
    finally:
        conn.close()
    response = decode_message(raw)
    if response.get("id") and response["id"] != request["id"]:
        raise RuntimeError("RPC response id mismatch")
    return response


def _start_daemon_process() -> None:
    cmd = [sys.executable, "-m", "desktop_cli.daemon"]
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen(
        cmd,
        creationflags=flags,
        close_fds=True,
        cwd=os.getcwd(),
        env=env,
    )


def _wait_until_ready() -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if ping(timeout=0.3):
            return
        time.sleep(0.15)
    raise RuntimeError(
        f"desktop daemon failed to start within {STARTUP_TIMEOUT}s. "
        f"Run: desktop-cli daemon status"
    )


def _startup_mutex():
    return _WindowsMutex()


class _WindowsMutex:
    def __init__(self) -> None:
        from desktop_cli.ipc.paths import mutex_name

        self._handle = None
        self._name = mutex_name()

    def __enter__(self) -> _WindowsMutex:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            raise RuntimeError("CreateMutex failed")
        self._handle = handle
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            # Another CLI is starting the daemon — wait for it.
            time.sleep(0.2)
        return self

    def __exit__(self, *args: object) -> None:
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)


def _terminate_pid(pid: Any) -> None:
    if not pid:
        return
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return
    kernel32 = ctypes.windll.kernel32
    PROCESS_TERMINATE = 0x0001
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid_int)
    if handle:
        kernel32.TerminateProcess(handle, 1)
        kernel32.CloseHandle(handle)


def register_daemon_pid(pid: int, address: tuple[str, int]) -> None:
    write_daemon_info(
        {
            "pid": pid,
            "address": {"host": address[0], "port": address[1]},
            "version": __version__,
            "started_at": time.time(),
        }
    )
