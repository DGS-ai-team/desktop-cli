"""Daemon in-memory state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import uiautomation as auto

from desktop_cli.lease import LeaseManager
from desktop_cli.refs import RefRegistry
from desktop_cli.target import TargetWindow


@dataclass
class DaemonState:
    lease: LeaseManager = field(default_factory=LeaseManager)
    refs: RefRegistry = field(default_factory=RefRegistry)
    target: TargetWindow = field(default_factory=TargetWindow)
    last_action: Optional[dict[str, Any]] = None

    def ensure_agent(self, agent_id: Optional[str]) -> None:
        from desktop_cli.lease import LeaseError
        from desktop_cli.output import CLIError, EXIT_LEASE

        try:
            self.lease.ensure(agent_id)
        except LeaseError as exc:
            raise CLIError(str(exc), EXIT_LEASE, data=exc.data) from exc

    def record_action(self, method: str, detail: dict[str, Any]) -> None:
        import time

        self.last_action = {"method": method, "detail": detail, "at": time.time()}

    def context(self) -> dict[str, Any]:
        fg = auto.GetForegroundControl()
        snap = self.refs.get_context()
        return {
            "target": self.target.to_dict(),
            "snapshot_id": snap.get("snapshot_id") or None,
            "ref_count": snap.get("ref_count", 0),
            "elements": snap.get("refs", []),
            "last_action": self.last_action,
            "foreground_handle": fg.NativeWindowHandle if fg else None,
        }
