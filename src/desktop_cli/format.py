"""Agent-browser-style text output and ref normalization."""

from __future__ import annotations

from typing import Any

from desktop_cli.compact import TYPE_SHORT, short_type


def normalize_ref(ref: str) -> str:
    """@e3 / e3 / 3 → internal e3."""
    ref = ref.strip()
    if ref.startswith("@"):
        ref = ref[1:]
    if ref.isdigit():
        return f"e{ref}"
    if not ref.startswith("e"):
        return f"e{ref}"
    return ref


def display_ref(ref: str) -> str:
    """e3 → @e3."""
    ref = normalize_ref(ref)
    return f"@{ref}"


def format_windows_text(windows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, w in enumerate(windows, 1):
        lines.append(f"{i}. {w.get('name', '')} ({w.get('handle', 0)})")
    return "\n".join(lines) if lines else "（无窗口）"


def format_snapshot_text(data: dict[str, Any]) -> str:
    window = data.get("window") or {}
    if isinstance(window, dict):
        win_name = window.get("name", "")
        win_handle = window.get("handle", 0)
    else:
        win_name = str(window)
        win_handle = data.get("h", 0)

    lines = [
        f"窗口: {win_name}",
        f"句柄: {win_handle}",
        "",
    ]
    for el in data.get("elements") or []:
        ref = display_ref(el.get("ref", ""))
        ctype = short_type(el.get("control_type", ""))
        name = el.get("name", "")
        aid = el.get("automation_id") or ""
        suffix = f" id={aid}" if aid else ""
        lines.append(f'{ref} [{ctype}] "{name}"{suffix}')

    if data.get("truncated"):
        lines.append("")
        lines.append("（已截断 — 使用 --max-elements 增大上限）")
    return "\n".join(lines)


def format_context_text(data: dict[str, Any]) -> str:
    target = data.get("target") or {}
    lines: list[str] = []
    if target.get("bound"):
        lines.append(f"窗口: {target.get('name', '')}")
        lines.append(f"句柄: {target.get('handle', 0)}")
    else:
        lines.append("窗口: （未绑定）")
    if data.get("snapshot_id"):
        lines.append(f"快照: {data.get('snapshot_id')}")
    if data.get("last_action"):
        la = data["last_action"]
        detail = la.get("detail") or {}
        if detail.get("ref"):
            lines.append(f"上次操作: {la.get('method')} {display_ref(str(detail['ref']))}")
        else:
            lines.append(f"上次操作: {la.get('method')}")
    elements = data.get("elements") or []
    if elements:
        lines.append("")
        for el in elements:
            ref = display_ref(el.get("ref", ""))
            ctype = short_type(el.get("control_type", ""))
            name = el.get("name", "")
            aid = el.get("automation_id") or ""
            suffix = f" id={aid}" if aid else ""
            lines.append(f'{ref} [{ctype}] "{name}"{suffix}')
    return "\n".join(lines)


def format_info_text(data: dict[str, Any]) -> str:
    lines = [
        f"用户: {data.get('username', '')}",
        f"会话: {data.get('session_id', '')} ({data.get('session_name', '')})",
        f"交互式: {'是' if data.get('interactive') else '否'}",
    ]
    for w in data.get("warnings") or []:
        lines.append(f"警告: {w}")
    return "\n".join(lines)


def format_health_text(data: dict[str, Any]) -> str:
    if not data.get("exists"):
        status = "窗口不存在"
    elif data.get("hung"):
        status = "未响应"
    elif data.get("slow"):
        status = "卡顿"
    elif data.get("responsive"):
        status = "正常"
    else:
        status = "异常"

    lines = [
        f"状态: {status}",
        f"窗口: {data.get('name', '')} ({data.get('handle', 0)})",
        f"探测耗时: {data.get('probe_ms', 0)}ms",
        f"未响应: {'是' if data.get('hung') else '否'}",
    ]
    if data.get("snapshot_id"):
        lines.append(f"快照: {data.get('snapshot_id')}")
    if data.get("snapshot_age_seconds") is not None:
        lines.append(f"快照年龄: {data.get('snapshot_age_seconds')}s")
    return "\n".join(lines)


def format_wait_text(data: dict[str, Any]) -> str:
    elapsed_s = (data.get("elapsed_ms") or 0) / 1000
    attempts = data.get("attempts", 0)
    match = data.get("match") or {}

    if data.get("mode") == "ref":
        ref = display_ref(data.get("ref", ""))
        name = match.get("name", "")
        return f"已就绪: {ref} \"{name}\" ({elapsed_s:.1f}s, {attempts}次)"

    text = data.get("text", "")
    ctype = short_type(match.get("control_type", ""))
    name = match.get("name", "")
    return f"已找到: \"{text}\" [{ctype}] \"{name}\" ({elapsed_s:.1f}s, {attempts}次)"


def format_action_text(data: dict[str, Any], *, verb: str) -> str:
    ref = display_ref(data.get("ref", ""))
    name = data.get("name", "")
    if data.get("dry_run"):
        return f"预检 {verb} {ref} \"{name}\""
    if verb == "filled":
        return f"已填入 {ref} \"{name}\""
    if verb == "typed" or data.get("typed") is not None:
        return f"已输入 {ref} \"{name}\""
    if verb == "clicked":
        return f"已点击 {ref} \"{name}\""
    return f"{verb} {ref} \"{name}\""


def format_response(command: str, data: Any) -> str:
    if command in ("windows", "windows.list"):
        if isinstance(data, dict) and "w" in data:
            return format_windows_text(
                [{"name": n, "handle": h} for n, h in data["w"]]
            )
        return format_windows_text(data if isinstance(data, list) else [])

    if command in ("open", "attach", "snapshot", "refresh"):
        if isinstance(data, dict) and "els" in data and "elements" not in data:
            data = _expand_compact_snapshot(data)
        return format_snapshot_text(data if isinstance(data, dict) else {})

    if command == "context":
        return format_context_text(data if isinstance(data, dict) else {})

    if command == "info":
        return format_info_text(data if isinstance(data, dict) else {})

    if command == "health":
        return format_health_text(data if isinstance(data, dict) else {})

    if command == "wait":
        return format_wait_text(data if isinstance(data, dict) else {})

    if command == "click":
        return format_action_text(data if isinstance(data, dict) else {}, verb="clicked")

    if command in ("type", "fill"):
        verb = "filled" if command == "fill" else "typed"
        return format_action_text(data if isinstance(data, dict) else {}, verb=verb)

    if isinstance(data, str):
        return data
    if data is None:
        return "OK"
    return str(data)


def _expand_compact_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    elements = []
    for row in data.get("els") or []:
        if not row:
            continue
        ref = row[0]
        ctype = row[1] if len(row) > 1 else ""
        name = row[2] if len(row) > 2 else ""
        aid = row[3] if len(row) > 3 else ""
        type_map = {v: k for k, v in TYPE_SHORT.items()}
        elements.append(
            {
                "ref": ref,
                "control_type": type_map.get(ctype, ctype),
                "name": name,
                "automation_id": aid,
            }
        )
    return {
        "window": {"name": data.get("win", ""), "handle": data.get("h", 0)},
        "snapshot_id": data.get("sid", ""),
        "elements": elements,
        "truncated": data.get("truncated", False),
    }
