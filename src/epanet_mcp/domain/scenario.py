"""Scenario lineage and change-manifest models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class ScenarioLineage:
    """Describe how a scenario was derived from a parent network."""

    parent_network_id: str
    scenario_type: str
    change_manifest: Dict[str, Any]
    topology: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_network_id": self.parent_network_id,
            "scenario_type": self.scenario_type,
            "change_manifest": self.change_manifest,
            "topology": self.topology,
        }
