"""Named-pipe RPC server for the desktop daemon."""

from __future__ import annotations

import os
import threading
import time
from multiprocessing.connection import Listener
from typing import Any

from desktop_cli import __version__
from desktop_cli.daemon.handlers import dispatch
from desktop_cli.daemon.state import DaemonState
from desktop_cli.ipc.client import register_daemon_pid
from desktop_cli.ipc.paths import authkey, remove_daemon_info
from desktop_cli.ipc.protocol import decode_message, encode_message
from desktop_cli.output import CLIError, EXIT_ERROR

_shutdown = threading.Event()
_state = DaemonState()
_lock = threading.Lock()


def _silence_uiautomation_logger() -> None:
    import uiautomation as auto

    auto.Logger.writeToFile = False
    auto.Logger.logFile = None
    for name in ("Write", "WriteLine", "ColorfullyWrite", "ColorfullyLog", "Log", "ColorfullyLog"):
        if hasattr(auto.Logger, name):
            setattr(auto.Logger, name, lambda *args, **kwargs: None)


def request_shutdown() -> None:
    _shutdown.set()


def is_shutdown_requested() -> bool:
    return _shutdown.is_set()


def run_server() -> None:
    _silence_uiautomation_logger()
    listener = Listener(("127.0.0.1", 0), authkey=authkey())
    register_daemon_pid(os.getpid(), listener.address)

    def accept_loop() -> None:
        while not _shutdown.is_set():
            try:
                conn = listener.accept()
            except (OSError, EOFError, ValueError):
                break
            threading.Thread(target=_handle_connection, args=(conn,), daemon=True).start()

    accept_thread = threading.Thread(target=accept_loop, daemon=True)
    accept_thread.start()
    try:
        while not _shutdown.is_set():
            time.sleep(0.2)
    finally:
        listener.close()
        accept_thread.join(timeout=1.0)
        remove_daemon_info()


def _handle_connection(conn) -> None:
    import comtypes

    comtypes.CoInitialize()
    try:
        if not conn.poll(30.0):
            return
        raw = conn.recv_bytes()
        request = decode_message(raw)
        response = _process_request(request)
        conn.send_bytes(encode_message(response))
    except Exception as exc:
        response = _error_response("", str(exc), EXIT_ERROR)
        try:
            conn.send_bytes(encode_message(response))
        except Exception:
            pass
    finally:
        conn.close()
        comtypes.CoUninitialize()


def _process_request(request: dict[str, Any]) -> dict[str, Any]:
    req_id = request.get("id", "")
    method = request.get("method", "")
    params = request.get("params") or {}
    start = time.perf_counter()

    try:
        with _lock:
            if method == "daemon.shutdown":
                data = dispatch(_state, method, params)
                request_shutdown()
            else:
                data = dispatch(_state, method, params)
        return {
            "id": req_id,
            "ok": True,
            "command": method,
            "data": data,
            "error": None,
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }
    except CLIError as exc:
        return {
            "id": req_id,
            "ok": False,
            "command": method,
            "data": exc.data,
            "error": str(exc),
            "exit_code": exc.exit_code,
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }
    except Exception as exc:
        return _error_response(req_id, str(exc), EXIT_ERROR, method)


def _error_response(req_id: str, error: str, exit_code: int, method: str = "") -> dict[str, Any]:
    return {
        "id": req_id,
        "ok": False,
        "command": method,
        "data": None,
        "error": error,
        "exit_code": exit_code,
    }
