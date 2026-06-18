"""Agent lease — single operator, auto-acquired silently."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional

DEFAULT_AGENT_ID = "default"
DEFAULT_TTL = 3600.0


@dataclass
class Lease:
    token: str
    agent_id: str
    acquired_at: float
    expires_at: float


@dataclass
class LeaseManager:
    _lease: Optional[Lease] = field(default=None, init=False)

    def ensure(self, agent_id: Optional[str] = None) -> None:
        """Auto-acquire or renew lease — no manual session step needed."""
        aid = agent_id or DEFAULT_AGENT_ID
        now = time.monotonic()
        self._cleanup_expired(now)

        if self._lease and self._lease.agent_id == aid:
            self._lease.expires_at = now + DEFAULT_TTL
            return

        if self._lease and self._lease.agent_id != aid:
            raise LeaseError(
                f"Desktop held by {self._lease.agent_id!r}. Wait or restart daemon.",
                data=self._status(now),
            )

        token = secrets.token_urlsafe(24)
        self._lease = Lease(
            token=token,
            agent_id=aid,
            acquired_at=now,
            expires_at=now + DEFAULT_TTL,
        )

    def status(self) -> dict[str, Any]:
        return self._status(time.monotonic())

    def _cleanup_expired(self, now: float) -> None:
        if self._lease and now >= self._lease.expires_at:
            self._lease = None

    def _status(self, now: float) -> dict[str, Any]:
        self._cleanup_expired(now)
        if not self._lease:
            return {"active": False}
        return {
            "active": True,
            "agent_id": self._lease.agent_id,
            "remaining_seconds": max(0, int(self._lease.expires_at - now)),
        }


class LeaseError(Exception):
    def __init__(self, message: str, *, code: str = "LEASE_ERROR", data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data
