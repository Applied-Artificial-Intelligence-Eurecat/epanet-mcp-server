"""Thread-safe lifecycle management for open ePyT network sessions."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Iterator, Optional

from epyt import epanet

from epanet_mcp.domain.scenario import ScenarioLineage


class SessionState(str, Enum):
    """Lifecycle states for an EPANET project handle."""

    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"


class NetworkSession:
    """Wrap an ePyT instance and serialize access to its project handle."""

    def __init__(
        self,
        network_id: str,
        path: str,
        d: epanet,
        lineage: Optional[ScenarioLineage] = None,
    ) -> None:
        self.network_id = network_id
        self.path = path
        self.d = d
        self.lineage = lineage
        self._operation_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._state = SessionState.ACTIVE
        self._active_operations = 0

    @property
    def state(self) -> SessionState:
        with self._state_lock:
            return self._state

    @property
    def active_operations(self) -> int:
        with self._state_lock:
            return self._active_operations

    @contextmanager
    def lease(self) -> Iterator[NetworkSession]:
        """Hold exclusive access to the handle for one complete operation."""
        with self._operation_lock:
            with self._state_lock:
                if self._state is not SessionState.ACTIVE:
                    raise RuntimeError(
                        f"Network session {self.network_id!r} is {self._state.value}."
                    )
                self._active_operations += 1
            try:
                yield self
            finally:
                with self._state_lock:
                    self._active_operations -= 1

    def close(self) -> bool:
        """Wait for the active operation, unload once, and mark the session closed."""
        with self._state_lock:
            if self._state is not SessionState.ACTIVE:
                return False
            self._state = SessionState.CLOSING

        with self._operation_lock:
            _safe_unload(self.d)
            with self._state_lock:
                self._state = SessionState.CLOSED
        return True

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"NetworkSession(id={self.network_id!r}, path={self.path!r}, "
            f"state={self.state.value!r})"
        )


class SessionRegistry:
    """Registry that owns sessions while operations lease their handles."""

    def __init__(self) -> None:
        self._sessions: Dict[str, NetworkSession] = {}
        self._lock = threading.RLock()
        self._local = threading.local()

    def _lease_stacks(self) -> Dict[str, list[NetworkSession]]:
        stacks = getattr(self._local, "lease_stacks", None)
        if stacks is None:
            stacks = {}
            self._local.lease_stacks = stacks
        return stacks

    def add(self, session: NetworkSession) -> None:
        """Publish a new session, rejecting an existing identifier."""
        with self._lock:
            if session.network_id in self._sessions:
                raise ValueError(
                    f"A network session with id={session.network_id!r} already exists. "
                    "Choose a different id or unload it first."
                )
            if session.state is not SessionState.ACTIVE:
                raise ValueError("Only active network sessions can be registered.")
            self._sessions[session.network_id] = session

    def replace(self, session: NetworkSession) -> bool:
        """Atomically publish ``session`` and then retire the previous value."""
        if session.state is not SessionState.ACTIVE:
            raise ValueError("Only active network sessions can be registered.")
        with self._lock:
            previous = self._sessions.get(session.network_id)
            self._sessions[session.network_id] = session
        if previous is not None and previous is not session:
            previous.close()
            return True
        return False

    def get(self, network_id: str) -> Optional[NetworkSession]:
        """Return a session for diagnostics; use ``lease`` for handle access."""
        with self._lock:
            return self._sessions.get(network_id)

    def require(self, network_id: str) -> NetworkSession:
        """Return a registered session without leasing its project handle."""
        stack = self._lease_stacks().get(network_id)
        if stack:
            # An in-flight operation keeps using the exact session it leased,
            # even after unload/replacement has unpublished that identifier.
            return stack[-1]
        with self._lock:
            session = self._sessions.get(network_id)
            if session is None:
                ids = list(self._sessions)
                raise ValueError(
                    f"No network loaded with id={network_id!r}. "
                    f"Loaded networks: {ids}. Use load_network first."
                )
            return session

    @contextmanager
    def lease(self, network_id: str) -> Iterator[NetworkSession]:
        """Lease a registered session for an entire ePyT operation."""
        stacks = self._lease_stacks()
        existing = stacks.get(network_id)
        if existing:
            session = existing[-1]
            existing.append(session)
            try:
                yield session
            finally:
                existing.pop()
            return

        session = self.require(network_id)
        with session.lease() as leased:
            stack = stacks.setdefault(network_id, [])
            stack.append(leased)
            try:
                yield leased
            finally:
                stack.pop()
                if not stack:
                    del stacks[network_id]

    def remove(self, network_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(network_id, None)
        if session is not None:
            session.close()
            return True
        return False

    def discard(self, session: NetworkSession) -> bool:
        """Remove ``session`` only if that exact object is currently published."""
        with self._lock:
            current = self._sessions.get(session.network_id)
            if current is not session:
                return False
            del self._sessions[session.network_id]
        session.close()
        return True

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._sessions)

    def clear(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()


def _safe_unload(d: epanet) -> None:
    """Unload an ePyT instance while keeping cleanup idempotent."""
    try:
        if hasattr(d, "api") and d.api is not None:
            d.unload()
    except Exception:
        # Cleanup must never mask the original tool or simulation error.
        pass


registry = SessionRegistry()


def session_operation(function: Callable[..., Any]) -> Callable[..., Any]:
    """Lease the first ``network_id`` argument for the full function call."""

    @wraps(function)
    def wrapped(network_id: str, *args: Any, **kwargs: Any) -> Any:
        with registry.lease(network_id):
            return function(network_id, *args, **kwargs)

    return wrapped
