"""Desktop daemon entry and lifecycle."""

from __future__ import annotations

import sys
import time

import uiautomation as auto

from desktop_cli.daemon.server import is_shutdown_requested, run_server
from desktop_cli.session import ensure_interactive

auto.Logger.writeToFile = False


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("desktop-cli daemon only supports Windows")
    ensure_interactive()
    run_server()
    # Allow in-flight RPCs to finish after shutdown request.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not is_shutdown_requested():
        time.sleep(0.05)


if __name__ == "__main__":
    main()
