"""
Session manager: holds open ePyT epanet instances keyed by session_id.

A single process-level registry lets all tool modules share the same loaded
networks without re-loading on every call.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional

from epyt import epanet


class NetworkSession:
    """Wraps an ePyT epanet instance with metadata."""

    def __init__(self, network_id: str, path: str, d: epanet) -> None:
        self.network_id = network_id
        self.path = path
        self.d = d

    def __repr__(self) -> str:  # pragma: no cover
        return f"NetworkSession(id={self.network_id!r}, path={self.path!r})"


class SessionRegistry:
    """Thread-safe registry of open network sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, NetworkSession] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # public helpers
    # ------------------------------------------------------------------

    def add(self, session: NetworkSession) -> None:
        with self._lock:
            self._sessions[session.network_id] = session

    def get(self, network_id: str) -> Optional[NetworkSession]:
        with self._lock:
            return self._sessions.get(network_id)

    def require(self, network_id: str) -> NetworkSession:
        """Return session or raise ValueError if unknown."""
        sess = self.get(network_id)
        if sess is None:
            ids = list(self._sessions.keys())
            raise ValueError(
                f"No network loaded with id={network_id!r}. "
                f"Loaded networks: {ids}. Use load_network first."
            )
        return sess

    def remove(self, network_id: str) -> bool:
        with self._lock:
            sess = self._sessions.pop(network_id, None)
            if sess is not None:
                _safe_unload(sess.d)
                return True
            return False

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())

    def clear(self) -> None:
        with self._lock:
            for sess in list(self._sessions.values()):
                _safe_unload(sess.d)
            self._sessions.clear()


def _safe_unload(d: epanet) -> None:
    """Unload an ePyT instance, suppressing any errors or C-level aborts."""
    try:
        # Check if the underlying api handle is still valid before calling unload
        if hasattr(d, "api") and d.api is not None:
            d.unload()
    except Exception:
        pass


# Module-level singleton used by all tool modules
registry = SessionRegistry()
