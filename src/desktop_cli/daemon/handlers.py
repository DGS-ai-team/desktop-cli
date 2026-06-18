"""RPC method handlers — background automation only."""

from __future__ import annotations

from typing import Any, Callable

from desktop_cli import __version__
from desktop_cli import session as session_mod
from desktop_cli import windows as windows_mod
from desktop_cli.daemon.state import DaemonState
from desktop_cli.format import normalize_ref
from desktop_cli.health import check_window_health
from desktop_cli.output import CLIError, EXIT_ERROR, EXIT_NOT_FOUND, EXIT_TIMEOUT
from desktop_cli.refs import RefError, click_ref, type_ref
from desktop_cli.wait_ui import wait_for_ref, wait_for_text

Handler = Callable[[DaemonState, dict[str, Any]], Any]

READ_METHODS = {
    "daemon.ping",
    "daemon.shutdown",
    "context.get",
    "windows.list",
    "health.get",
    "wait",
}


def dispatch(state: DaemonState, method: str, params: dict[str, Any]) -> Any:
    handler = HANDLERS.get(method)
    if not handler:
        raise CLIError(f"Unknown method: {method}", EXIT_ERROR)

    if method not in READ_METHODS:
        state.ensure_agent(params.get("agent_id"))

    result = handler(state, params)
    if method not in ("daemon.ping", "daemon.shutdown", "context.get", "health.get", "wait"):
        state.record_action(method, _action_detail(params))
    return result


def _action_detail(params: dict[str, Any]) -> dict[str, Any]:
    keys = ("ref", "title", "handle", "text")
    return {k: params[k] for k in keys if k in params and params[k] is not None}


def _handle_ping(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "pong": True,
        "version": __version__,
        "session": session_mod.get_session_info(),
        "target": state.target.to_dict(),
        "snapshot_id": state.refs.snapshot_id or None,
    }


def _handle_shutdown(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    return {"shutting_down": True}


def _handle_context_get(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    return state.context()


def _handle_windows_list(state: DaemonState, params: dict[str, Any]) -> list[dict[str, Any]]:
    session_mod.ensure_interactive()
    return windows_mod.list_windows(visible_only=not params.get("all", False))


def _snapshot_payload(state: DaemonState, handle: int, max_elements: int) -> dict[str, Any]:
    snap = state.refs.build_snapshot(handle=handle, max_elements=max_elements)
    return {
        "snapshot_id": snap["snapshot_id"],
        "window": snap["window"],
        "count": snap["count"],
        "truncated": snap.get("truncated", False),
        "elements": snap["elements"],
    }


def _handle_attach(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    session_mod.ensure_interactive()
    title = params.get("title")
    handle = params.get("handle")
    if not title and handle is None:
        raise CLIError("请提供 --title 或 --handle", EXIT_ERROR)

    state.target.bind(title=title, handle=handle)
    return _snapshot_payload(
        state,
        state.target.handle,
        int(params.get("max_elements", 200)),
    )


def _handle_refresh(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    session_mod.ensure_interactive()
    if not state.target.is_bound():
        raise CLIError("未绑定窗口，请先 open", EXIT_NOT_FOUND)
    return _snapshot_payload(
        state,
        state.target.handle,
        int(params.get("max_elements", 200)),
    )


def _handle_click(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    session_mod.ensure_interactive()
    ref = normalize_ref(params.get("ref") or "")
    if not ref:
        raise CLIError("缺少 ref 参数", EXIT_ERROR)
    if not state.target.is_bound():
        raise CLIError("未绑定窗口，请先 open", EXIT_NOT_FOUND)
    try:
        return click_ref(state.refs, ref, dry_run=bool(params.get("dry_run", False)), background=True)
    except RefError as exc:
        code = EXIT_NOT_FOUND if exc.code == "REF_UNKNOWN" else EXIT_ERROR
        raise CLIError(str(exc), code, data=exc.data) from exc


def _handle_type(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    session_mod.ensure_interactive()
    ref = normalize_ref(params.get("ref") or "")
    text = params.get("text", "")
    if not ref:
        raise CLIError("缺少 ref 参数", EXIT_ERROR)
    if not state.target.is_bound():
        raise CLIError("未绑定窗口，请先 open", EXIT_NOT_FOUND)
    try:
        return type_ref(state.refs, ref, text, clear=bool(params.get("clear", False)))
    except RefError as exc:
        code = EXIT_NOT_FOUND if exc.code == "REF_UNKNOWN" else EXIT_ERROR
        raise CLIError(str(exc), code, data=exc.data) from exc


def _handle_health(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    session_mod.ensure_interactive()
    if not state.target.is_bound():
        raise CLIError("未绑定窗口，请先 open", EXIT_NOT_FOUND)

    import time

    health = check_window_health(state.target.handle)
    health["window"] = state.target.name
    health["snapshot_id"] = state.refs.snapshot_id or None
    if state.refs.created_at:
        health["snapshot_age_seconds"] = int(time.time() - state.refs.created_at)
    return health


def _handle_wait(state: DaemonState, params: dict[str, Any]) -> dict[str, Any]:
    session_mod.ensure_interactive()
    if not state.target.is_bound():
        raise CLIError("未绑定窗口，请先 open", EXIT_NOT_FOUND)

    text = params.get("text")
    ref = params.get("ref")
    timeout = float(params.get("timeout", 10.0))
    interval = float(params.get("interval", 0.5))

    if text and ref:
        raise CLIError("请指定 --text 或 --ref 之一，不要同时使用", EXIT_ERROR)
    if not text and not ref:
        raise CLIError("请提供等待文本或 --ref", EXIT_ERROR)

    if ref:
        result = wait_for_ref(
            state.refs,
            state.target.handle,
            ref,
            timeout=timeout,
            interval=interval,
        )
    else:
        result = wait_for_text(
            state.target.handle,
            text,
            timeout=timeout,
            interval=interval,
        )

    if result.get("found") is False:
        if result.get("mode") == "ref":
            msg = f"等待超时 ({timeout}s)：ref {ref!r} 仍不可用"
        else:
            msg = f"等待超时 ({timeout}s)：未找到文本 {text!r}"
        raise CLIError(msg, EXIT_TIMEOUT, data=result)

    return result


HANDLERS: dict[str, Handler] = {
    "daemon.ping": _handle_ping,
    "daemon.shutdown": _handle_shutdown,
    "context.get": _handle_context_get,
    "windows.list": _handle_windows_list,
    "attach": _handle_attach,
    "refresh": _handle_refresh,
    "click": _handle_click,
    "type": _handle_type,
    "health.get": _handle_health,
    "wait": _handle_wait,
}
