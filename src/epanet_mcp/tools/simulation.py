"""
Tools for running EPANET hydraulic and water-quality simulations.
"""

from __future__ import annotations

from typing import Any, Dict

from epanet_mcp.engine import runner
from epanet_mcp.session import NetworkSession
from epanet_mcp.session import registry
from epanet_mcp.utils import safe_list, to_python

# ---------------------------------------------------------------------------
# Full time-series simulations
# ---------------------------------------------------------------------------


def run_hydraulic_simulation(network_id: str) -> Dict[str, Any]:
    """
    Run a full hydraulic simulation and return time-series results.

    Returns pressures, demands, heads, flows, velocities, head-losses
    and link statuses at every reporting time step.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network (see ``load_network``).
    """
    with registry.lease(network_id) as session:
        return _run_hydraulic_session(session)


def _run_hydraulic_session(session: NetworkSession) -> Dict[str, Any]:
    """Run hydraulics for an already leased session."""

    def operation(d: Any) -> Dict[str, Any]:
        ts = d.getComputedHydraulicTimeSeries()
        return {
            "network_id": session.network_id,
            "time_steps_s": safe_list(ts.Time),
            "node_ids": safe_list(d.getNodeNameID()),
            "link_ids": safe_list(d.getLinkNameID()),
            "pressure": to_python(ts.Pressure),
            "demand": to_python(ts.Demand),
            "head": to_python(ts.Head),
            "flow": to_python(ts.Flow),
            "velocity": to_python(ts.Velocity),
            "head_loss": to_python(ts.HeadLoss),
            "status": to_python(ts.Status),
            "setting": to_python(ts.Setting),
        }

    return runner.run_on_snapshot(session, operation)


def run_quality_simulation(network_id: str) -> Dict[str, Any]:
    """
    Run a full water-quality simulation and return time-series results.

    Includes node and link quality concentrations in addition to all
    hydraulic results.  The quality type must be configured in the .inp
    file (or via ``set_quality_type``).

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    """
    with registry.lease(network_id) as session:
        return _run_quality_session(session)


def _run_quality_session(session: NetworkSession) -> Dict[str, Any]:
    """Run water quality for an already leased session."""

    def operation(d: Any) -> Dict[str, Any]:
        ts = d.getComputedQualityTimeSeries()
        return {
            "network_id": session.network_id,
            "time_steps_s": safe_list(ts.Time),
            "node_ids": safe_list(d.getNodeNameID()),
            "link_ids": safe_list(d.getLinkNameID()),
            "node_quality": to_python(ts.NodeQuality),
            "link_quality": to_python(ts.LinkQuality),
            "mass_flow_rate": to_python(ts.MassFlowRate),
        }

    return runner.run_on_snapshot(session, operation)


def run_full_simulation(network_id: str) -> Dict[str, Any]:
    """
    Run both hydraulic and water-quality simulations in one call.

    Returns the combined time-series including pressures, demands, heads,
    flows, velocities, head-losses, node/link quality and reaction rates.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    """
    with registry.lease(network_id) as session:
        return _run_full_session(session)


def _run_full_session(session: NetworkSession) -> Dict[str, Any]:
    """Run hydraulics and quality for an already leased session."""

    def operation(d: Any) -> Dict[str, Any]:
        ts = d.getComputedTimeSeries()
        return {
            "network_id": session.network_id,
            "time_steps_s": safe_list(ts.Time),
            "node_ids": safe_list(d.getNodeNameID()),
            "link_ids": safe_list(d.getLinkNameID()),
            "pressure": to_python(ts.Pressure),
            "demand": to_python(ts.Demand),
            "head": to_python(ts.Head),
            "node_quality": to_python(ts.NodeQuality),
            "flow": to_python(ts.Flow),
            "velocity": to_python(ts.Velocity),
            "head_loss": to_python(ts.HeadLoss),
            "link_quality": to_python(ts.LinkQuality),
            "status": to_python(ts.Status),
            "setting": to_python(ts.Setting),
            "reaction_rate": to_python(ts.ReactionRate),
            "friction_factor": to_python(ts.FrictionFactor),
        }

    return runner.run_on_snapshot(session, operation)


# ---------------------------------------------------------------------------
# Step-by-step / single snapshot
# ---------------------------------------------------------------------------


def get_pressure_at_time(
    network_id: str,
    time_s: int,
) -> Dict[str, Any]:
    """
    Return node pressures at (or nearest to) a specific simulation time.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    time_s:
        Simulation time in seconds.
    """
    with registry.lease(network_id) as session:
        result = _run_hydraulic_session(session)
        times = result["time_steps_s"]
        pressures = result["pressure"]
        node_ids = result["node_ids"]
        closest_idx = min(range(len(times)), key=lambda i: abs(times[i] - time_s))
        row = pressures[closest_idx] if pressures else []
        return {
            "network_id": network_id,
            "requested_time_s": time_s,
            "actual_time_s": times[closest_idx],
            "pressures": {
                node_id: row[i] for i, node_id in enumerate(node_ids) if i < len(row)
            },
        }


def get_flow_at_time(
    network_id: str,
    time_s: int,
) -> Dict[str, Any]:
    """
    Return link flows at (or nearest to) a specific simulation time.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    time_s:
        Simulation time in seconds.
    """
    with registry.lease(network_id) as session:
        result = _run_hydraulic_session(session)
        times = result["time_steps_s"]
        flows = result["flow"]
        link_ids = result["link_ids"]
        closest_idx = min(range(len(times)), key=lambda i: abs(times[i] - time_s))
        row = flows[closest_idx] if flows else []
        return {
            "network_id": network_id,
            "requested_time_s": time_s,
            "actual_time_s": times[closest_idx],
            "flows": {
                link_id: row[i] for i, link_id in enumerate(link_ids) if i < len(row)
            },
        }
