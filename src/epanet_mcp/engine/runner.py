"""Isolate solver workspaces and construction of independent ePyT handles."""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from typing import Callable, TypeVar

from epyt import epanet

from epanet_mcp.session import NetworkSession

T = TypeVar("T")

# ``os.chdir`` is process-wide. Until ePyT exposes an explicit output path for
# every generated artifact, directory-changing solver calls share one lock.
_WORKSPACE_LOCK = threading.RLock()


class EpanetRunner:
    """Execute EPANET solver calls in a private, serialized workspace."""

    def run(self, operation: Callable[[], T]) -> T:
        with _WORKSPACE_LOCK:
            previous_cwd = os.getcwd()
            with tempfile.TemporaryDirectory(prefix="epanet-mcp-run-") as directory:
                os.chdir(directory)
                try:
                    return operation()
                finally:
                    os.chdir(previous_cwd)

    def run_on_snapshot(
        self,
        session: NetworkSession,
        operation: Callable[[epanet], T],
        epanet_factory: Callable[..., epanet] = epanet,
    ) -> T:
        """Run a leased editable session through an isolated solver handle.

        ePyT's stepwise hydraulic API is not project-handle aware. Editable
        sessions therefore use ``ph=True``, while each simulation uses a
        temporary ``ph=False`` snapshot under the process-wide runner lock.
        """

        def execute() -> T:
            snapshot_path = Path.cwd() / "network.inp"
            session.d.saveInputFile(str(snapshot_path))
            solver = epanet_factory(
                str(snapshot_path),
                display_msg=False,
                display_warnings=False,
                ph=False,
            )
            try:
                return operation(solver)
            finally:
                try:
                    solver.unload()
                except Exception:
                    pass

        return self.run(execute)

    def clone_session(
        self,
        source: NetworkSession,
        new_id: str,
        epanet_factory: Callable[..., epanet] = epanet,
    ) -> NetworkSession:
        """Clone a leased source session without publishing the clone."""
        temporary_path: Path | None = None
        new_handle: epanet | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".inp", delete=False) as tmp:
                temporary_path = Path(tmp.name)
            source.d.saveInputFile(str(temporary_path))
            new_handle = epanet_factory(str(temporary_path), display_msg=False, ph=True)
            return NetworkSession(new_id, source.path, new_handle)
        except Exception:
            if new_handle is not None:
                try:
                    new_handle.unload()
                except Exception:
                    pass
            raise
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


runner = EpanetRunner()
