"""Tests for agent lease manager."""

import pytest

from desktop_cli.lease import LeaseError, LeaseManager


def test_auto_acquire():
    mgr = LeaseManager()
    mgr.ensure("agent-a")
    status = mgr.status()
    assert status["active"] is True
    assert status["agent_id"] == "agent-a"


def test_conflict_raises():
    mgr = LeaseManager()
    mgr.ensure("agent-a")
    with pytest.raises(LeaseError):
        mgr.ensure("agent-b")
