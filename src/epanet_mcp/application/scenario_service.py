"""Transactional construction and publication of scenario sessions."""

from __future__ import annotations

from types import TracebackType
from typing import Optional, Type

from epanet_mcp.domain.scenario import ScenarioLineage
from epanet_mcp.engine import runner
from epanet_mcp.session import NetworkSession, registry


class ScenarioTransaction:
    """Keep a cloned scenario private until every requested step succeeds."""

    def __init__(self, source_id: str, scenario_id: str) -> None:
        self.source_id = source_id
        self.scenario_id = scenario_id
        self.session: Optional[NetworkSession] = None
        self._lease = None
        self._committed = False

    def __enter__(self) -> ScenarioTransaction:
        with registry.lease(self.source_id) as source:
            self.session = runner.clone_session(source, self.scenario_id)
        self._lease = self.session.lease()
        self._lease.__enter__()
        return self

    @property
    def d(self):
        if self.session is None:
            raise RuntimeError("Scenario transaction has not started.")
        return self.session.d

    def commit(self, lineage: ScenarioLineage) -> NetworkSession:
        if self.session is None:
            raise RuntimeError("Scenario transaction has not started.")
        self.session.lineage = lineage
        registry.add(self.session)
        self._committed = True
        return self.session

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        if self._lease is not None:
            self._lease.__exit__(exc_type, exc, traceback)
        if self.session is not None and (exc_type is not None or not self._committed):
            if self._committed:
                registry.discard(self.session)
            else:
                self.session.close()
        return False
