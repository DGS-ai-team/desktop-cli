"""Tests for IPC message encoding."""

from desktop_cli.ipc.protocol import decode_message, encode_message, make_request


def test_request_roundtrip():
    req = make_request("attach", {"title": "Notepad"})
    raw = encode_message(req)
    decoded = decode_message(raw)
    assert decoded["method"] == "attach"
    assert decoded["params"]["title"] == "Notepad"
    assert decoded["id"] == req["id"]


def test_unicode_roundtrip():
    payload = make_request("type", {"text": "中文"})
    decoded = decode_message(encode_message(payload))
    assert decoded["params"]["text"] == "中文"
