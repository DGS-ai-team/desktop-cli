"""JSON-line RPC message helpers."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional


def make_request(method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "method": method,
        "params": params or {},
    }


def encode_message(payload: dict[str, Any]) -> bytes:
    text = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    return text.encode("utf-8", errors="replace")


def decode_message(raw: bytes) -> dict[str, Any]:
    return json.loads(raw.decode("utf-8"))
