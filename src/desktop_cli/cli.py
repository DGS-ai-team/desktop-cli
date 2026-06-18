"""Typer CLI — 供 AI Agent 使用的 Windows 后台桌面自动化。"""

from __future__ import annotations

from typing import Any, Optional

import typer

from desktop_cli import __version__
from desktop_cli import session as session_mod
from desktop_cli.compact import (
    compact_action_result,
    compact_context,
    compact_health,
    compact_snapshot,
    compact_wait,
    compact_windows,
)
from desktop_cli.format import format_response
from desktop_cli.ipc import client as ipc_client
from desktop_cli.lease import DEFAULT_AGENT_ID
from desktop_cli.output import CLIError, EXIT_ERROR, OutputFormat, failure, success, timed
from desktop_cli.util import ensure_utf8_stdio

ensure_utf8_stdio()

app = typer.Typer(
    name="desktop-cli",
    help="Windows 后台桌面自动化 CLI，供 AI Agent 通过 Shell 调用。",
    no_args_is_help=True,
    add_completion=False,
)

daemon_app = typer.Typer(help="Daemon 运维命令。", hidden=True)
app.add_typer(daemon_app, name="daemon")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def main(
    ctx: typer.Context,
    agent_id: str = typer.Option(
        DEFAULT_AGENT_ID,
        "--agent-id",
        help="Agent 标识，用于 lease 互斥（默认 default）。",
        envvar="DESKTOP_CLI_AGENT_ID",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="输出 JSON 而非纯文本（默认纯文本，省 token）。",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="完整 JSON 字段（需与 --json 一起使用）。",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="显示版本并退出。",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["agent_id"] = agent_id
    if json_output:
        ctx.obj["fmt"] = "json-full" if full else "json"
    else:
        ctx.obj["fmt"] = "text"


def _output_fmt(ctx: typer.Context) -> OutputFormat:
    return (ctx.obj or {}).get("fmt", "text")


def _params(ctx: typer.Context, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    payload = dict(extra or {})
    payload.setdefault("agent_id", (ctx.obj or {}).get("agent_id", DEFAULT_AGENT_ID))
    return payload


def _compact_data(command: str, data: Any) -> Any:
    if command in ("windows", "windows.list"):
        return compact_windows(data if isinstance(data, list) else [])
    if command in ("open", "attach", "snapshot", "refresh"):
        return compact_snapshot(data if isinstance(data, dict) else {})
    if command == "context":
        return compact_context(data if isinstance(data, dict) else {})
    if command in ("click", "type", "fill"):
        return compact_action_result(data if isinstance(data, dict) else {})
    if command == "health":
        return compact_health(data if isinstance(data, dict) else {})
    if command == "wait":
        return compact_wait(data if isinstance(data, dict) else {})
    return data


def _emit_rpc_response(
    command: str,
    response: dict[str, Any],
    *,
    fmt: OutputFormat,
    pretty: bool,
) -> None:
    duration = response.get("duration_ms")
    if response.get("ok"):
        data = response.get("data")
        if fmt == "text":
            success(command, data, fmt=fmt, text=format_response(command, data))
        elif fmt == "json":
            success(command, _compact_data(command, data), fmt=fmt, pretty=pretty, duration_ms=duration)
        else:
            success(command, data, fmt=fmt, pretty=pretty, duration_ms=duration)
    failure(
        command,
        response.get("error") or "未知错误",
        exit_code=int(response.get("exit_code", EXIT_ERROR)),
        data=response.get("data"),
        fmt=fmt,
        pretty=pretty,
        duration_ms=duration,
    )


def _rpc(
    ctx: typer.Context,
    command: str,
    method: str,
    params: Optional[dict[str, Any]] = None,
) -> None:
    payload = dict(params or {})
    pretty = bool(payload.pop("_pretty", False))
    fmt = _output_fmt(ctx)
    payload = _params(ctx, payload)
    try:
        with timed() as t:
            response = ipc_client.call(method, payload)
        if response.get("duration_ms") is None:
            response["duration_ms"] = t.duration_ms
        _emit_rpc_response(command, response, fmt=fmt, pretty=pretty)
    except SystemExit:
        raise
    except Exception as exc:
        failure(command, str(exc), fmt=fmt, pretty=pretty)


def _run_local(
    command: str,
    pretty: bool,
    fn,
    *,
    fmt: OutputFormat = "text",
) -> None:
    try:
        with timed() as t:
            data = fn()
        if fmt == "text":
            success(command, data, fmt=fmt, text=format_response(command, data))
        elif fmt == "json":
            success(command, _compact_data(command, data), fmt=fmt, pretty=pretty, duration_ms=t.duration_ms)
        else:
            success(command, data, fmt=fmt, pretty=pretty, duration_ms=t.duration_ms)
    except CLIError as exc:
        failure(
            command,
            str(exc),
            exit_code=exc.exit_code,
            data=exc.data,
            fmt=fmt,
            pretty=pretty,
        )
    except SystemExit:
        raise
    except Exception as exc:
        failure(command, str(exc), fmt=fmt, pretty=pretty)


# --- Agent 命令 ---


@app.command("windows")
def cmd_windows(
    ctx: typer.Context,
    all_windows: bool = typer.Option(False, "--all", help="包含无标题窗口。"),
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """列出当前打开的窗口。"""
    _rpc(ctx, "windows", "windows.list", {"all": all_windows, "_pretty": pretty})


@app.command("open")
def cmd_open(
    ctx: typer.Context,
    title: Optional[str] = typer.Option(None, "--title", "-t", help="窗口标题子串。"),
    handle: Optional[int] = typer.Option(None, "--handle", help="窗口句柄。"),
    max_elements: int = typer.Option(200, "--max-elements", help="快照最大元素数。"),
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """绑定窗口并生成 UI 快照（不抢焦点）。"""
    _rpc(
        ctx,
        "open",
        "attach",
        {"title": title, "handle": handle, "max_elements": max_elements, "_pretty": pretty},
    )


@app.command("attach", hidden=True)
def cmd_attach(
    ctx: typer.Context,
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    handle: Optional[int] = typer.Option(None, "--handle"),
    max_elements: int = typer.Option(200, "--max-elements"),
    pretty: bool = typer.Option(False, "--pretty"),
) -> None:
    """open 的别名。"""
    cmd_open(ctx, title=title, handle=handle, max_elements=max_elements, pretty=pretty)


@app.command("snapshot")
def cmd_snapshot(
    ctx: typer.Context,
    max_elements: int = typer.Option(200, "--max-elements", help="快照最大元素数。"),
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """UI 变化后重新快照已绑定窗口。"""
    _rpc(ctx, "snapshot", "refresh", {"max_elements": max_elements, "_pretty": pretty})


@app.command("refresh", hidden=True)
def cmd_refresh(
    ctx: typer.Context,
    max_elements: int = typer.Option(200, "--max-elements"),
    pretty: bool = typer.Option(False, "--pretty"),
) -> None:
    """snapshot 的别名。"""
    cmd_snapshot(ctx, max_elements=max_elements, pretty=pretty)


@app.command("click")
def cmd_click(
    ctx: typer.Context,
    ref: str = typer.Argument(..., help="元素 ref，如 @e3 或 e3。"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅预检目标，不实际点击。"),
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """按 ref 后台点击元素。"""
    _rpc(ctx, "click", "click", {"ref": ref, "dry_run": dry_run, "_pretty": pretty})


@app.command("fill")
def cmd_fill(
    ctx: typer.Context,
    ref: str = typer.Argument(..., help="元素 ref，如 @e3。"),
    text: str = typer.Argument(..., help="要填入的文本（先清空再输入）。"),
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """清空控件并输入文本。"""
    _rpc(ctx, "fill", "type", {"ref": ref, "text": text, "clear": True, "_pretty": pretty})


@app.command("type")
def cmd_type(
    ctx: typer.Context,
    ref: str = typer.Argument(..., help="元素 ref，如 @e3。"),
    text: str = typer.Argument(..., help="要追加的文本。"),
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """向控件追加输入文本。"""
    _rpc(ctx, "type", "type", {"ref": ref, "text": text, "clear": False, "_pretty": pretty})


@app.command("wait")
def cmd_wait(
    ctx: typer.Context,
    text: Optional[str] = typer.Argument(None, help="等待出现的界面文本（子串匹配）。"),
    ref: Optional[str] = typer.Option(None, "--ref", "-r", help="等待 ref 可解析。"),
    timeout: float = typer.Option(10.0, "--timeout", help="超时秒数。"),
    interval: float = typer.Option(0.5, "--interval", help="轮询间隔（秒）。"),
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """等待 UI 就绪（文本出现或 ref 可解析）。超时退出码 2。"""
    _rpc(
        ctx,
        "wait",
        "wait",
        {"text": text, "ref": ref, "timeout": timeout, "interval": interval, "_pretty": pretty},
    )


@app.command("health")
def cmd_health(
    ctx: typer.Context,
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """检测已绑定窗口是否响应（未响应/卡顿/正常）。"""
    _rpc(ctx, "health", "health.get", {"_pretty": pretty})


@app.command("context")
def cmd_context(
    ctx: typer.Context,
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """查看当前绑定窗口、refs 与上次操作。"""
    _rpc(ctx, "context", "context.get", {"_pretty": pretty})


@app.command("info")
def cmd_info(
    ctx: typer.Context,
    pretty: bool = typer.Option(False, "--pretty", help="格式化 JSON（需 --json）。"),
) -> None:
    """本地会话诊断（不经过 daemon）。"""
    _run_local("info", pretty, session_mod.get_session_info, fmt=_output_fmt(ctx))


# --- 运维（隐藏） ---


@daemon_app.command("status")
def daemon_status(ctx: typer.Context, pretty: bool = typer.Option(False, "--pretty")) -> None:
    _run_local("daemon.status", pretty, ipc_client.daemon_status, fmt=_output_fmt(ctx))


@daemon_app.command("stop")
def daemon_stop(ctx: typer.Context, pretty: bool = typer.Option(False, "--pretty")) -> None:
    def _fn():
        ipc_client.stop_daemon()
        return {"stopped": True}

    _run_local("daemon.stop", pretty, _fn, fmt=_output_fmt(ctx))


if __name__ == "__main__":
    app()
