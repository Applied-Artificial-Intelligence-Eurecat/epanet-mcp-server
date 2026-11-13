"""Tests for solver workspace isolation and clone cleanup."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from epanet_mcp.engine.runner import EpanetRunner
from epanet_mcp.session import NetworkSession


class SavingHandle:
    def __init__(self) -> None:
        self.api = object()
        self.saved_path: Path | None = None

    def saveInputFile(self, path: str) -> None:
        self.saved_path = Path(path)
        self.saved_path.write_text("[TITLE]\nclone test\n")


class SolverHandle:
    def __init__(self) -> None:
        self.unloaded = False

    def unload(self) -> None:
        self.unloaded = True


def test_runner_serializes_directory_changes_and_restores_cwd():
    epanet_runner = EpanetRunner()
    original_cwd = os.getcwd()
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    workspaces: list[str] = []

    def first_operation() -> None:
        workspaces.append(os.getcwd())
        first_started.set()
        assert release_first.wait(timeout=2)

    def second_operation() -> None:
        workspaces.append(os.getcwd())
        second_started.set()

    first = threading.Thread(target=lambda: epanet_runner.run(first_operation))
    second = threading.Thread(target=lambda: epanet_runner.run(second_operation))
    first.start()
    assert first_started.wait(timeout=2)
    second.start()

    assert not second_started.wait(timeout=0.05)
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert second_started.is_set()
    assert len(set(workspaces)) == 2
    assert all(path != original_cwd for path in workspaces)
    assert os.getcwd() == original_cwd
    assert all(not Path(path).exists() for path in workspaces)


def test_runner_restores_cwd_when_operation_fails():
    epanet_runner = EpanetRunner()
    original_cwd = os.getcwd()

    with pytest.raises(RuntimeError, match="solver failed"):
        epanet_runner.run(lambda: (_ for _ in ()).throw(RuntimeError("solver failed")))

    assert os.getcwd() == original_cwd


def test_run_on_snapshot_uses_solver_handle_and_always_unloads():
    epanet_runner = EpanetRunner()
    editable = SavingHandle()
    source = NetworkSession("source", "/source.inp", editable)
    solver = SolverHandle()
    factory_calls = []

    def factory(path, **kwargs):
        factory_calls.append((Path(path), kwargs))
        return solver

    with source.lease():
        with pytest.raises(RuntimeError, match="simulation failed"):
            epanet_runner.run_on_snapshot(
                source,
                lambda _solver: (_ for _ in ()).throw(
                    RuntimeError("simulation failed")
                ),
                factory,
            )

    snapshot_path, options = factory_calls[0]
    assert snapshot_path.name == "network.inp"
    assert options["ph"] is False
    assert solver.unloaded is True
    assert not snapshot_path.exists()


def test_clone_removes_temporary_input_when_loading_fails():
    epanet_runner = EpanetRunner()
    handle = SavingHandle()
    source = NetworkSession("source", "/source.inp", handle)

    def fail_to_load(*args, **kwargs):
        raise RuntimeError("load failed")

    with source.lease():
        with pytest.raises(RuntimeError, match="load failed"):
            epanet_runner.clone_session(source, "clone", fail_to_load)

    assert handle.saved_path is not None
    assert not handle.saved_path.exists()
