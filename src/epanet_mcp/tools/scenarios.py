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

import uuid
from math import ceil
from typing import Any, Callable, Dict, List, Optional

from epanet_mcp.application.scenario_service import ScenarioTransaction
from epanet_mcp.domain.scenario import ScenarioLineage
from epanet_mcp.domain.validation import (
    choice,
    finite_number,
    integer_value,
    link_index,
    node_index,
    nonempty_string,
    nonnegative_number,
    positive_number,
)
from epanet_mcp.tools.simulation import _run_full_session, _run_hydraulic_session
from epanet_mcp.utils import safe_list, to_python

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scenario_id(explicit_id: Optional[str], base: str) -> str:
    """Keep explicit IDs stable and make generated IDs collision-resistant."""
    return explicit_id or f"{base}_{uuid.uuid4().hex[:8]}"


def _create_scenario(
    source_id: str,
    scenario_id: str,
    run_simulation: bool,
    build: Callable[[Any], Dict[str, Any]],
) -> Dict[str, Any]:
    """Build, optionally simulate, and only then publish a scenario."""
    with ScenarioTransaction(source_id, scenario_id) as transaction:
        result = build(transaction.d)
        if run_simulation:
            assert transaction.session is not None
            result["simulation"] = _run_full_session(transaction.session)
        _commit_scenario(transaction, result)
        return result


def _commit_scenario(transaction: ScenarioTransaction, result: Dict[str, Any]) -> None:
    manifest = result.setdefault("change_manifest", {"operations": []})
    topology = result.setdefault("topology", {})
    lineage = ScenarioLineage(
        parent_network_id=transaction.source_id,
        scenario_type=result["scenario_type"],
        change_manifest=manifest,
        topology=topology,
    )
    result["lineage"] = lineage.to_dict()
    transaction.commit(lineage)


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
    sid = _scenario_id(scenario_id, f"{network_id}_demand_pert")

    def build(d: Any) -> Dict[str, Any]:
        if not node_demands:
            raise ValueError("node_demands must contain at least one node multiplier.")
        validated: list[tuple[str, int, float]] = []
        for node_id, multiplier in node_demands.items():
            idx = node_index(d, node_id, kind="junction")
            validated.append(
                (
                    node_id,
                    idx,
                    nonnegative_number(f"node_demands[{node_id!r}]", multiplier),
                )
            )

        changed: Dict[str, Any] = {}
        operations = []
        for node_id, idx, multiplier in validated:
            all_demands = d.getNodeBaseDemands()[1]
            old_demand = float(all_demands[idx - 1])
            new_demand = old_demand * multiplier
            d.setNodeBaseDemands(idx, new_demand)
            changed[node_id] = {
                "old_demand": old_demand,
                "new_demand": new_demand,
            }
            operations.append(
                {
                    "action": "set",
                    "asset_type": "node",
                    "asset_id": node_id,
                    "field": "base_demand",
                    "category": 1,
                    "old_value": old_demand,
                    "new_value": new_demand,
                }
            )
        return {
            "scenario_type": "demand_perturbation",
            "scenario_id": sid,
            "changes": changed,
            "change_manifest": {"operations": operations},
        }

    return _create_scenario(network_id, sid, run_simulation, build)


# ---------------------------------------------------------------------------
# Leakage events
# ---------------------------------------------------------------------------


def create_leakage_event(
    network_id: str,
    pipe_id: str,
    leak_fraction: Optional[float] = None,
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
    target_leak_flow: Optional[float] = None,
    reference_pressure: Optional[float] = None,
    emitter_exponent: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Simulate a pipe burst / leakage by splitting a pipe and adding an
    emitter to the midpoint node.

    The leak is modelled as ``Q = C * P^gamma`` at a midpoint junction.
    Supply either ``target_leak_flow`` directly or ``leak_fraction`` to derive
    the target from the baseline mean absolute pipe flow.

    Parameters
    ----------
    network_id:
        Source network id.
    pipe_id:
        Id of the pipe that develops the leak.
    leak_fraction:
        Optional fraction of baseline mean absolute pipe flow (0.0–1.0).
    scenario_id:
        Id for the new cloned scenario session.
    run_simulation:
        Run a full simulation after applying the changes.
    target_leak_flow:
        Optional target leak flow in the network's flow units.
    reference_pressure:
        Pressure at which the target leak flow applies. If omitted, it is
        derived from the baseline mean pressure at both pipe endpoints.
    emitter_exponent:
        Pressure exponent. Defaults to the model's configured exponent.
    """
    if (leak_fraction is None) == (target_leak_flow is None):
        raise ValueError("Provide exactly one of leak_fraction or target_leak_flow.")
    if leak_fraction is not None:
        leak_fraction = finite_number("leak_fraction", leak_fraction)
        if not 0.0 <= leak_fraction <= 1.0:
            raise ValueError("leak_fraction must be between 0.0 and 1.0.")
    if target_leak_flow is not None:
        target_leak_flow = nonnegative_number("target_leak_flow", target_leak_flow)
    if reference_pressure is not None:
        reference_pressure = positive_number("reference_pressure", reference_pressure)
    if emitter_exponent is not None:
        emitter_exponent = positive_number("emitter_exponent", emitter_exponent)

    sid = _scenario_id(scenario_id, f"{network_id}_leak_{pipe_id}")

    with ScenarioTransaction(network_id, sid) as transaction:
        d = transaction.d
        pipe_idx = link_index(d, pipe_id, kind="pipe")
        from_idx, to_idx = d.getLinkNodesIndex()[pipe_idx - 1]
        node_names = safe_list(d.getNodeNameID())
        from_node = node_names[from_idx - 1]
        to_node = node_names[to_idx - 1]
        elevations = safe_list(d.getNodeElevations())
        coordinates = d.getNodeCoordinates()
        mid_coordinates = [
            (coordinates[axis][from_idx] + coordinates[axis][to_idx]) / 2.0
            for axis in ("x", "y")
        ]
        baseline = None
        if leak_fraction is not None or reference_pressure is None:
            assert transaction.session is not None
            baseline = _run_hydraulic_session(transaction.session)

        mean_pipe_flow = None
        if leak_fraction is not None:
            assert baseline is not None
            link_position = baseline["link_ids"].index(pipe_id)
            pipe_flows = [abs(float(row[link_position])) for row in baseline["flow"]]
            mean_pipe_flow = sum(pipe_flows) / len(pipe_flows)
            target_leak_flow = leak_fraction * mean_pipe_flow

        if reference_pressure is None:
            assert baseline is not None
            from_position = baseline["node_ids"].index(from_node)
            to_position = baseline["node_ids"].index(to_node)
            midpoint_pressures = [
                (float(row[from_position]) + float(row[to_position])) / 2.0
                for row in baseline["pressure"]
            ]
            positive_pressures = [value for value in midpoint_pressures if value > 0]
            if not positive_pressures:
                raise ValueError(
                    "Cannot derive a positive reference pressure from the baseline. "
                    "Provide reference_pressure explicitly."
                )
            reference_pressure = sum(positive_pressures) / len(positive_pressures)

        exponent = emitter_exponent or positive_number(
            "model emitter exponent", to_python(d.getOptionsEmitterExponent())
        )
        if emitter_exponent is not None:
            d.setOptionsEmitterExponent(exponent)
        assert target_leak_flow is not None
        assert reference_pressure is not None
        emitter_coeff = target_leak_flow / (reference_pressure**exponent)

        mid_elevation = (elevations[from_idx - 1] + elevations[to_idx - 1]) / 2.0
        mid_node_id = f"Leak_{pipe_id}"
        if mid_node_id in node_names:
            raise ValueError(f"Leak node id={mid_node_id!r} already exists.")
        d.addNodeJunction(mid_node_id, mid_coordinates, mid_elevation, 0.0)
        mid_idx = node_index(d, mid_node_id, kind="junction")
        d.setNodeEmitterCoeff(mid_idx, emitter_coeff)
        orig_length = to_python(d.getLinkLength(pipe_idx))
        orig_diameter = to_python(d.getLinkDiameter(pipe_idx))
        orig_roughness = to_python(d.getLinkRoughnessCoeff(pipe_idx))
        orig_minor_loss = to_python(d.getLinkMinorLossCoeff(pipe_idx))
        orig_status = to_python(d.getLinkInitialStatus(pipe_idx))
        orig_bulk_reaction = to_python(d.getLinkBulkReactionCoeff(pipe_idx))
        orig_wall_reaction = to_python(d.getLinkWallReactionCoeff(pipe_idx))
        half_length = orig_length / 2.0
        p1_id = f"{pipe_id}_A"
        p2_id = f"{pipe_id}_B"
        existing_links = safe_list(d.getLinkNameID())
        collisions = [
            link_id for link_id in (p1_id, p2_id) if link_id in existing_links
        ]
        if collisions:
            raise ValueError(f"Split-pipe ids already exist: {collisions}")
        d.addLinkPipe(
            p1_id, from_node, mid_node_id, half_length, orig_diameter, orig_roughness
        )
        d.addLinkPipe(
            p2_id, mid_node_id, to_node, half_length, orig_diameter, orig_roughness
        )
        p1_idx = link_index(d, p1_id, kind="pipe")
        p2_idx = link_index(d, p2_id, kind="pipe")
        for new_pipe_idx in (p1_idx, p2_idx):
            d.setLinkMinorLossCoeff(new_pipe_idx, orig_minor_loss / 2.0)
            d.setLinkInitialStatus(new_pipe_idx, orig_status)
            d.setLinkBulkReactionCoeff(new_pipe_idx, orig_bulk_reaction)
            d.setLinkWallReactionCoeff(new_pipe_idx, orig_wall_reaction)
        d.deleteLink(pipe_idx)

        flow_units = d.getFlowUnits()
        pressure_units = _pressure_units(flow_units)
        result: Dict[str, Any] = {
            "scenario_type": "leakage_event",
            "scenario_id": sid,
            "pipe_id": pipe_id,
            "leak_fraction": leak_fraction,
            "baseline_mean_pipe_flow": mean_pipe_flow,
            "target_leak_flow": target_leak_flow,
            "reference_pressure": reference_pressure,
            "emitter_exponent": exponent,
            "leak_node": mid_node_id,
            "emitter_coeff": emitter_coeff,
            "units": {
                "flow": flow_units,
                "pressure": pressure_units,
                "emitter_coefficient": f"{flow_units}/{pressure_units}^{exponent:g}",
            },
            "pipe_split_into": [p1_id, p2_id],
            "change_manifest": {
                "operations": [
                    {
                        "action": "replace",
                        "asset_type": "pipe",
                        "asset_id": pipe_id,
                        "replacement_ids": [p1_id, p2_id],
                    },
                    {
                        "action": "add",
                        "asset_type": "node",
                        "asset_id": mid_node_id,
                        "field": "emitter_coefficient",
                        "new_value": emitter_coeff,
                    },
                ]
            },
            "topology": {
                "added_nodes": [mid_node_id],
                "removed_links": [pipe_id],
                "added_links": [p1_id, p2_id],
                "link_replacements": {pipe_id: [p1_id, p2_id]},
            },
        }
        if run_simulation:
            assert transaction.session is not None
            result["simulation"] = _run_full_session(transaction.session)
        _commit_scenario(transaction, result)
        return result


def _pressure_units(flow_units: str) -> str:
    return "ft" if flow_units in {"CFS", "GPM", "MGD", "IMGD", "AFD"} else "m"


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
    chemical_name: str = "Contaminant",
    units: str = "mg/L",
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
    chemical_name:
        Chemical species name stored in the EPANET model.
    units:
        Chemical concentration units for the model.
    """
    source_type = choice(
        "source_type", source_type, ("CONCEN", "MASS", "FLOWPACED", "SETPOINT")
    )
    concentration = nonnegative_number("concentration", concentration)
    start_time_s = integer_value("start_time_s", start_time_s)
    end_time_s = integer_value("end_time_s", end_time_s)
    chemical_name = nonempty_string("chemical_name", chemical_name)
    units = nonempty_string("units", units)
    if end_time_s <= start_time_s:
        raise ValueError("end_time_s must be greater than start_time_s.")

    sid = _scenario_id(scenario_id, f"{network_id}_contam_{source_node_id}")

    def build(d: Any) -> Dict[str, Any]:
        node_idx = node_index(d, source_node_id)
        pattern_step = int(to_python(d.getTimePatternStep()))
        pattern_start = int(to_python(d.getTimePatternStart()))
        duration = int(to_python(d.getTimeSimulationDuration()))
        if end_time_s > duration:
            raise ValueError(
                f"end_time_s ({end_time_s}) exceeds simulation duration ({duration})."
            )
        for name, value in (("start_time_s", start_time_s), ("end_time_s", end_time_s)):
            if (value + pattern_start) % pattern_step != 0:
                raise ValueError(
                    f"{name}={value} is not aligned to the {pattern_step}-second "
                    f"pattern timestep (pattern start={pattern_start})."
                )

        d.setQualityType("CHEM", chemical_name, units)
        first_active_period = (start_time_s + pattern_start) // pattern_step
        first_inactive_period = (end_time_s + pattern_start) // pattern_step
        n_periods = max(1, ceil((duration + pattern_start) / pattern_step))
        pattern_values = [0.0] * n_periods
        for period in range(first_active_period, first_inactive_period):
            pattern_values[period] = 1.0
        pat_id = f"ContamPat_{source_node_id}"
        try:
            d.addPattern(pat_id, pattern_values)
        except Exception:
            pidx = d.getPatternIndex(pat_id)
            d.setPattern(pidx, pattern_values)
        pat_idx = d.getPatternIndex(pat_id)
        d.setNodeSourceQuality(node_idx, concentration)
        d.setNodeSourceType(node_idx, source_type)
        d.setNodeSourcePatternIndex(node_idx, pat_idx)
        return {
            "scenario_type": "contamination_event",
            "scenario_id": sid,
            "source_node_id": source_node_id,
            "concentration": concentration,
            "start_time_s": start_time_s,
            "end_time_s": end_time_s,
            "source_type": source_type,
            "source_strength_units": ("mass/min" if source_type == "MASS" else units),
            "chemical_name": chemical_name,
            "quality_units": units,
            "pattern_id": pat_id,
            "pattern_timestep_s": pattern_step,
            "pattern_values": pattern_values,
            "change_manifest": {
                "operations": [
                    {
                        "action": "set",
                        "asset_type": "node",
                        "asset_id": source_node_id,
                        "field": "quality_source",
                        "source_type": source_type,
                        "source_strength": concentration,
                        "pattern_id": pat_id,
                    }
                ]
            },
        }

    return _create_scenario(network_id, sid, run_simulation, build)


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
    sid = _scenario_id(scenario_id, f"{network_id}_pressure")

    def build(d: Any) -> Dict[str, Any]:
        if not reservoir_heads:
            raise ValueError("reservoir_heads must contain at least one reservoir.")
        validated = [
            (
                reservoir_id,
                node_index(d, reservoir_id, kind="reservoir"),
                finite_number(f"reservoir_heads[{reservoir_id!r}]", head),
            )
            for reservoir_id, head in reservoir_heads.items()
        ]
        changes: Dict[str, Any] = {}
        operations = []
        for res_id, idx, new_head in validated:
            old_head = to_python(d.getNodeElevations(idx))
            d.setNodeElevations(idx, new_head)
            changes[res_id] = {"old_head": old_head, "new_head": new_head}
            operations.append(
                {
                    "action": "set",
                    "asset_type": "reservoir",
                    "asset_id": res_id,
                    "field": "head",
                    "old_value": old_head,
                    "new_value": new_head,
                }
            )
        return {
            "scenario_type": "pressure_change",
            "scenario_id": sid,
            "changes": changes,
            "change_manifest": {"operations": operations},
        }

    return _create_scenario(network_id, sid, run_simulation, build)


# ---------------------------------------------------------------------------
# Pump control scenario
# ---------------------------------------------------------------------------


def create_pump_control_scenario(
    network_id: str,
    pump_schedule: Dict[str, List[str]],
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
    sid = _scenario_id(scenario_id, f"{network_id}_pump_sched")

    def build(d: Any) -> Dict[str, Any]:
        if not pump_schedule:
            raise ValueError("pump_schedule must contain at least one pump.")
        validated: list[tuple[str, list[str]]] = []
        for pump_id, controls in pump_schedule.items():
            link_index(d, pump_id, kind="pump")
            if not controls:
                raise ValueError(f"pump_schedule[{pump_id!r}] must not be empty.")
            validated.append(
                (
                    pump_id,
                    [
                        nonempty_string(f"pump_schedule[{pump_id!r}] control", control)
                        for control in controls
                    ],
                )
            )
        added_controls: Dict[str, list] = {}
        operations = []
        for pump_id, controls in validated:
            added_controls[pump_id] = []
            for ctrl_str in controls:
                idx = d.addControls(ctrl_str)
                added_controls[pump_id].append(
                    {"control": ctrl_str, "index": to_python(idx)}
                )
                operations.append(
                    {
                        "action": "add",
                        "asset_type": "control",
                        "asset_id": to_python(idx),
                        "target_type": "pump",
                        "target_id": pump_id,
                        "control": ctrl_str,
                    }
                )
        return {
            "scenario_type": "pump_control",
            "scenario_id": sid,
            "added_controls": added_controls,
            "change_manifest": {"operations": operations},
        }

    return _create_scenario(network_id, sid, run_simulation, build)


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
    sid = _scenario_id(scenario_id, f"{network_id}_valve")

    def build(d: Any) -> Dict[str, Any]:
        if not valve_settings:
            raise ValueError("valve_settings must contain at least one valve.")
        validated = [
            (
                valve_id,
                link_index(d, valve_id, kind="valve"),
                finite_number(f"valve_settings[{valve_id!r}]", setting),
            )
            for valve_id, setting in valve_settings.items()
        ]
        changes: Dict[str, Any] = {}
        operations = []
        for valve_id, idx, setting in validated:
            old = to_python(d.getLinkInitialSetting(idx))
            d.setLinkInitialSetting(idx, setting)
            changes[valve_id] = {"old_setting": old, "new_setting": setting}
            operations.append(
                {
                    "action": "set",
                    "asset_type": "valve",
                    "asset_id": valve_id,
                    "field": "initial_setting",
                    "old_value": old,
                    "new_value": setting,
                }
            )
        return {
            "scenario_type": "valve_control",
            "scenario_id": sid,
            "changes": changes,
            "change_manifest": {"operations": operations},
        }

    return _create_scenario(network_id, sid, run_simulation, build)


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
    sid = _scenario_id(scenario_id, f"{network_id}_failure")

    def build(d: Any) -> Dict[str, Any]:
        if not failed_pipes and not failed_pumps:
            raise ValueError("At least one failed pipe or pump must be provided.")
        pipe_indices = [
            (pipe_id, link_index(d, pipe_id, kind="pipe"))
            for pipe_id in failed_pipes or []
        ]
        pump_indices = [
            (pump_id, link_index(d, pump_id, kind="pump"))
            for pump_id in failed_pumps or []
        ]
        closed: Dict[str, list] = {"pipes": [], "pumps": []}
        operations = []
        for pipe_id, idx in pipe_indices:
            d.setLinkInitialStatus(idx, 0)
            closed["pipes"].append(pipe_id)
            operations.append(
                {
                    "action": "set",
                    "asset_type": "pipe",
                    "asset_id": pipe_id,
                    "field": "initial_status",
                    "new_value": "CLOSED",
                }
            )
        for pump_id, idx in pump_indices:
            d.setLinkInitialStatus(idx, 0)
            closed["pumps"].append(pump_id)
            operations.append(
                {
                    "action": "set",
                    "asset_type": "pump",
                    "asset_id": pump_id,
                    "field": "initial_status",
                    "new_value": "CLOSED",
                }
            )
        return {
            "scenario_type": "multi_failure",
            "scenario_id": sid,
            "closed": closed,
            "change_manifest": {"operations": operations},
        }

    return _create_scenario(network_id, sid, run_simulation, build)
