"""Concurrency and lifecycle tests for network sessions."""

from __future__ import annotations

import threading

import pytest

from epanet_mcp.session import NetworkSession, SessionRegistry, SessionState


class FakeHandle:
    def __init__(self) -> None:
        self.api = object()
        self.unload_count = 0
        self.unloaded = threading.Event()

    def unload(self) -> None:
        self.unload_count += 1
        self.unloaded.set()


def test_remove_waits_for_active_lease_before_unload():
    registry = SessionRegistry()
    handle = FakeHandle()
    session = NetworkSession("network", "/network.inp", handle)
    registry.add(session)
    operation_started = threading.Event()
    release_operation = threading.Event()
    remove_finished = threading.Event()

    def operate() -> None:
        with registry.lease("network"):
            operation_started.set()
            assert release_operation.wait(timeout=2)

    def remove() -> None:
        registry.remove("network")
        remove_finished.set()

    operation_thread = threading.Thread(target=operate)
    operation_thread.start()
    assert operation_started.wait(timeout=2)

    remove_thread = threading.Thread(target=remove)
    remove_thread.start()
    assert not remove_finished.wait(timeout=0.05)
    assert not handle.unloaded.is_set()
    assert "network" not in registry.list_ids()

    release_operation.set()
    operation_thread.join(timeout=2)
    remove_thread.join(timeout=2)

    assert remove_finished.is_set()
    assert handle.unload_count == 1
    assert session.state is SessionState.CLOSED


def test_active_lease_keeps_session_after_unpublication():
    registry = SessionRegistry()
    session = NetworkSession("network", "/network.inp", FakeHandle())
    registry.add(session)
    remove_started = threading.Event()
    remove_finished = threading.Event()

    def remove() -> None:
        remove_started.set()
        registry.remove("network")
        remove_finished.set()

    with registry.lease("network"):
        remove_thread = threading.Thread(target=remove)
        remove_thread.start()
        assert remove_started.wait(timeout=2)
        for _ in range(100):
            if "network" not in registry.list_ids():
                break
            threading.Event().wait(0.001)

        assert "network" not in registry.list_ids()
        assert registry.require("network") is session
        with registry.lease("network") as nested:
            assert nested is session
        assert not remove_finished.is_set()

    remove_thread.join(timeout=2)
    assert remove_finished.is_set()


def test_add_rejects_collision_without_unloading_existing_session():
    registry = SessionRegistry()
    original_handle = FakeHandle()
    original = NetworkSession("network", "/original.inp", original_handle)
    candidate = NetworkSession("network", "/candidate.inp", FakeHandle())
    registry.add(original)

    with pytest.raises(ValueError, match="already exists"):
        registry.add(candidate)

    assert registry.require("network") is original
    assert original.state is SessionState.ACTIVE
    assert original_handle.unload_count == 0


def test_replace_publishes_new_session_and_closes_previous_one():
    registry = SessionRegistry()
    old_handle = FakeHandle()
    old = NetworkSession("network", "/old.inp", old_handle)
    new = NetworkSession("network", "/new.inp", FakeHandle())
    registry.add(old)

    assert registry.replace(new) is True

    assert registry.require("network") is new
    assert old.state is SessionState.CLOSED
    assert old_handle.unload_count == 1
