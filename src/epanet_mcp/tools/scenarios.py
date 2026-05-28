"""
Tools for generating EPANET simulation scenarios.

Each scenario function works by:
  1. Copying a baseline network session (or using the original).
  2. Applying the prescribed perturbations.
  3. Running a simulation.
  4. Returning the results together with a description of what was changed.

The caller can pass ``run_simulation=True`` (default) to get results
immediately, or ``False`` to just apply the modifications and inspect/save.
"""

from __future__ import annotations

import copy
import os
import tempfile
from typing import Any, Dict, List, Optional

from epyt import epanet

from epanet_mcp.session import NetworkSession, registry
from epanet_mcp.tools.simulation import run_full_simulation
from epanet_mcp.utils import safe_list, to_python

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clone_session(source_id: str, new_id: str) -> NetworkSession:
    """
    Clone a session by saving to a temp file and re-loading.

    This gives a fully independent ePyT instance.
    """
    src = registry.require(source_id)
    tmp = tempfile.NamedTemporaryFile(suffix=".inp", delete=False)
    tmp.close()
    src.d.saveInputFile(tmp.name)
    d_new = epanet(tmp.name, display_msg=False, ph=True)
    os.unlink(tmp.name)
    sess = NetworkSession(network_id=new_id, path=src.path, d=d_new)
    registry.add(sess)
    return sess


def _maybe_run(network_id: str, run_simulation: bool) -> Optional[Dict[str, Any]]:
    if run_simulation:
        return run_full_simulation(network_id)
    return None


# ---------------------------------------------------------------------------
# Demand perturbation
# ---------------------------------------------------------------------------


def create_demand_perturbation(
    network_id: str,
    node_demands: Dict[str, float],
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Apply base-demand multipliers to a set of nodes and optionally simulate.

    Each entry in ``node_demands`` specifies a **multiplier** relative to the
    current base demand (1.0 = no change, 2.0 = double demand, 0.0 = no
    demand).

    Parameters
    ----------
    network_id:
        Source network id to perturb (a clone is created automatically).
    node_demands:
        Mapping of ``{node_id: multiplier}``.
    scenario_id:
        Id for the new cloned scenario session.  Auto-generated if omitted.
    run_simulation:
        Run a full simulation after applying the changes.
    """
    sid = scenario_id or f"{network_id}_demand_pert"
    sess = _clone_session(network_id, sid)
    d = sess.d

    changed: Dict[str, Any] = {}
    for node_id, multiplier in node_demands.items():
        idx = d.getNodeIndex(node_id)
        # getNodeBaseDemands()[1] returns a list indexed by node order
        all_demands = d.getNodeBaseDemands()[1]
        old_demand = float(all_demands[idx - 1])  # idx is 1-based
        new_demand = old_demand * multiplier
        d.setNodeBaseDemands(idx, new_demand)
        changed[node_id] = {"old_demand": old_demand, "new_demand": new_demand}

    result: Dict[str, Any] = {
        "scenario_type": "demand_perturbation",
        "scenario_id": sid,
        "changes": changed,
    }
    sim = _maybe_run(sid, run_simulation)
    if sim:
        result["simulation"] = sim
    return result


# ---------------------------------------------------------------------------
# Leakage events
# ---------------------------------------------------------------------------


def create_leakage_event(
    network_id: str,
    pipe_id: str,
    leak_fraction: float,
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Simulate a pipe burst / leakage by splitting a pipe and adding an
    emitter to the midpoint node.

    The leak is modelled as an emitter coefficient on the midpoint junction.
    ``leak_fraction`` is the fraction of the pipe's average flow that leaks
    (0.0–1.0).

    Parameters
    ----------
    network_id:
        Source network id.
    pipe_id:
        Id of the pipe that develops the leak.
    leak_fraction:
        Fraction of average flow that becomes the leak (0.0–1.0).
    scenario_id:
        Id for the new cloned scenario session.
    run_simulation:
        Run a full simulation after applying the changes.
    """
    if not 0.0 <= leak_fraction <= 1.0:
        raise ValueError("leak_fraction must be between 0.0 and 1.0")

    sid = scenario_id or f"{network_id}_leak_{pipe_id}"
    sess = _clone_session(network_id, sid)
    d = sess.d

    # Get pipe info
    pipe_idx = d.getLinkIndex(pipe_id)
    node_pairs = d.getLinkNodesIndex()
    from_idx, to_idx = node_pairs[pipe_idx - 1]
    node_names = safe_list(d.getNodeNameID())

    from_node = node_names[from_idx - 1]
    to_node = node_names[to_idx - 1]
    elevations = safe_list(d.getNodeElevations())

    # Add a midpoint junction
    mid_elevation = (elevations[from_idx - 1] + elevations[to_idx - 1]) / 2.0
    mid_node_id = f"Leak_{pipe_id}"
    d.addNodeJunction(mid_node_id, [mid_elevation, 0.0])
    mid_idx = d.getNodeIndex(mid_node_id)

    # Add emitter (leak) — coefficient scales with leak_fraction
    # We use a nominal emitter coefficient; real calibration would use pressure data
    emitter_coeff = leak_fraction * 10.0  # approximate; adjust per application
    d.setNodeEmitterCoeff(mid_idx, emitter_coeff)  # (nodeIndex, value)

    # Split the original pipe into two halves
    orig_length = to_python(d.getLinkLength(pipe_idx))
    orig_diameter = to_python(d.getLinkDiameter(pipe_idx))
    orig_roughness = to_python(d.getLinkRoughnessCoeff(pipe_idx))

    half_length = orig_length / 2.0

    # Add two new pipes
    p1_id = f"{pipe_id}_A"
    p2_id = f"{pipe_id}_B"
    d.addLinkPipe(
        p1_id, from_node, mid_node_id, half_length, orig_diameter, orig_roughness
    )
    d.addLinkPipe(
        p2_id, mid_node_id, to_node, half_length, orig_diameter, orig_roughness
    )

    # Delete original pipe
    d.deleteLink(pipe_idx)

    result: Dict[str, Any] = {
        "scenario_type": "leakage_event",
        "scenario_id": sid,
        "pipe_id": pipe_id,
        "leak_fraction": leak_fraction,
        "leak_node": mid_node_id,
        "emitter_coeff": emitter_coeff,
        "pipe_split_into": [p1_id, p2_id],
    }
    sim = _maybe_run(sid, run_simulation)
    if sim:
        result["simulation"] = sim
    return result


# ---------------------------------------------------------------------------
# Contamination events
# ---------------------------------------------------------------------------


def create_contamination_event(
    network_id: str,
    source_node_id: str,
    concentration: float,
    start_time_s: int,
    end_time_s: int,
    source_type: str = "CONCEN",
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Inject a contaminant at a node for a specified time window.

    The quality type is set to ``CHEM`` automatically (named ``Contaminant``).

    Parameters
    ----------
    network_id:
        Source network id.
    source_node_id:
        Node where the contaminant is introduced.
    concentration:
        Contaminant concentration (mg/L or model's quality units).
    start_time_s:
        Time (seconds from start) when the injection begins.
    end_time_s:
        Time (seconds from start) when the injection ends.
    source_type:
        EPANET source type: ``"CONCEN"``, ``"MASS"``, ``"FLOWPACED"``,
        or ``"SETPOINT"``.
    scenario_id:
        Id for the new cloned scenario session.
    run_simulation:
        Run a full simulation after applying the changes.
    """
    sid = scenario_id or f"{network_id}_contam_{source_node_id}"
    sess = _clone_session(network_id, sid)
    d = sess.d

    # ensure quality is set to chemical
    d.setQualityType("CHEM", "Contaminant", "mg/L")

    node_idx = d.getNodeIndex(source_node_id)

    # Build a source pattern: 1 during injection window, 0 otherwise
    hstep = to_python(d.getTimeHydraulicStep())
    duration = to_python(d.getTimeSimulationDuration())

    n_steps = max(1, int(duration // hstep) + 1)
    pattern_values = []
    for i in range(n_steps):
        t = i * hstep
        pattern_values.append(1.0 if start_time_s <= t <= end_time_s else 0.0)

    # add pattern for the source
    pat_id = f"ContamPat_{source_node_id}"
    try:
        d.addPattern(pat_id, pattern_values)
    except Exception:
        # pattern may already exist; update it
        pidx = d.getPatternIndex(pat_id)
        d.setPattern(pidx, pattern_values)

    pat_idx = d.getPatternIndex(pat_id)
    d.setNodeSourceQuality(node_idx, concentration)  # (nodeIndex, value)
    d.setNodeSourceType(node_idx, source_type)  # (nodeIndex, typeString)
    d.setNodeSourcePatternIndex(node_idx, pat_idx)  # (nodeIndex, patternIndex)

    result: Dict[str, Any] = {
        "scenario_type": "contamination_event",
        "scenario_id": sid,
        "source_node_id": source_node_id,
        "concentration": concentration,
        "start_time_s": start_time_s,
        "end_time_s": end_time_s,
        "source_type": source_type,
        "pattern_id": pat_id,
    }
    sim = _maybe_run(sid, run_simulation)
    if sim:
        result["simulation"] = sim
    return result


# ---------------------------------------------------------------------------
# Pressure change scenario
# ---------------------------------------------------------------------------


def create_pressure_change_scenario(
    network_id: str,
    reservoir_heads: Dict[str, float],
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Create a scenario with modified reservoir heads to study pressure changes.

    Parameters
    ----------
    network_id:
        Source network id.
    reservoir_heads:
        Mapping of ``{reservoir_id: new_head}``.
    scenario_id:
        Id for the new cloned scenario session.
    run_simulation:
        Run a full simulation after applying the changes.
    """
    sid = scenario_id or f"{network_id}_pressure"
    sess = _clone_session(network_id, sid)
    d = sess.d

    changes: Dict[str, Any] = {}
    for res_id, new_head in reservoir_heads.items():
        idx = d.getNodeIndex(res_id)
        old_head = to_python(d.getNodeElevations(idx))
        d.setNodeElevations(idx, new_head)
        changes[res_id] = {"old_head": old_head, "new_head": new_head}

    result: Dict[str, Any] = {
        "scenario_type": "pressure_change",
        "scenario_id": sid,
        "changes": changes,
    }
    sim = _maybe_run(sid, run_simulation)
    if sim:
        result["simulation"] = sim
    return result


# ---------------------------------------------------------------------------
# Pump control scenario
# ---------------------------------------------------------------------------


def create_pump_control_scenario(
    network_id: str,
    pump_schedule: Dict[str, List[Dict[str, Any]]],
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Apply a time-based pump on/off or speed schedule.

    Each pump's schedule is a list of control rules in plain-text EPANET
    syntax, e.g.::

        {
            "Pump9": [
                "LINK Pump9 1.0 AT TIME 06:00",
                "LINK Pump9 CLOSED AT TIME 22:00",
            ]
        }

    Parameters
    ----------
    network_id:
        Source network id.
    pump_schedule:
        Mapping of ``{pump_id: [control_string, ...]}``.
    scenario_id:
        Id for the new cloned scenario session.
    run_simulation:
        Run a full simulation after applying the changes.
    """
    sid = scenario_id or f"{network_id}_pump_sched"
    sess = _clone_session(network_id, sid)
    d = sess.d

    added_controls: Dict[str, list] = {}
    for pump_id, controls in pump_schedule.items():
        added_controls[pump_id] = []
        for ctrl_str in controls:
            idx = d.addControls(ctrl_str)
            added_controls[pump_id].append(
                {"control": ctrl_str, "index": to_python(idx)}
            )

    result: Dict[str, Any] = {
        "scenario_type": "pump_control",
        "scenario_id": sid,
        "added_controls": added_controls,
    }
    sim = _maybe_run(sid, run_simulation)
    if sim:
        result["simulation"] = sim
    return result


# ---------------------------------------------------------------------------
# Valve control scenario
# ---------------------------------------------------------------------------


def create_valve_control_scenario(
    network_id: str,
    valve_settings: Dict[str, float],
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Apply static valve setting changes and simulate.

    Parameters
    ----------
    network_id:
        Source network id.
    valve_settings:
        Mapping of ``{valve_id: new_setting}``.
    scenario_id:
        Id for the new cloned scenario session.
    run_simulation:
        Run a full simulation after applying the changes.
    """
    sid = scenario_id or f"{network_id}_valve"
    sess = _clone_session(network_id, sid)
    d = sess.d

    changes: Dict[str, Any] = {}
    for valve_id, setting in valve_settings.items():
        idx = d.getLinkIndex(valve_id)
        old = to_python(d.getLinkInitialSetting(idx))
        d.setLinkInitialSetting(idx, setting)
        changes[valve_id] = {"old_setting": old, "new_setting": setting}

    result: Dict[str, Any] = {
        "scenario_type": "valve_control",
        "scenario_id": sid,
        "changes": changes,
    }
    sim = _maybe_run(sid, run_simulation)
    if sim:
        result["simulation"] = sim
    return result


# ---------------------------------------------------------------------------
# Multiple-failure scenario
# ---------------------------------------------------------------------------


def create_multi_failure_scenario(
    network_id: str,
    failed_pipes: Optional[List[str]] = None,
    failed_pumps: Optional[List[str]] = None,
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Simulate simultaneous pipe and/or pump failures (closure).

    Parameters
    ----------
    network_id:
        Source network id.
    failed_pipes:
        List of pipe ids to close.
    failed_pumps:
        List of pump ids to close.
    scenario_id:
        Id for the new cloned scenario session.
    run_simulation:
        Run a full simulation after applying the changes.
    """
    sid = scenario_id or f"{network_id}_failure"
    sess = _clone_session(network_id, sid)
    d = sess.d

    closed: Dict[str, list] = {"pipes": [], "pumps": []}
    for pid in failed_pipes or []:
        idx = d.getLinkIndex(pid)
        d.setLinkInitialStatus(idx, 0)
        closed["pipes"].append(pid)
    for pid in failed_pumps or []:
        idx = d.getLinkIndex(pid)
        d.setLinkInitialStatus(idx, 0)
        closed["pumps"].append(pid)

    result: Dict[str, Any] = {
        "scenario_type": "multi_failure",
        "scenario_id": sid,
        "closed": closed,
    }
    sim = _maybe_run(sid, run_simulation)
    if sim:
        result["simulation"] = sim
    return result
