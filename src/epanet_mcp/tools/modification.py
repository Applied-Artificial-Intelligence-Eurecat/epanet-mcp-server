"""
Tools for modifying an EPANET network model in-memory via ePyT.

All modifications operate on a loaded session and do not persist to disk
unless ``save_network`` is called.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from epanet_mcp.session import registry
from epanet_mcp.utils import safe_list, to_python


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_network(network_id: str, output_path: str) -> Dict[str, Any]:
    """
    Save the current (possibly modified) network to a new .inp file.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    output_path:
        Destination file path (must end with ``.inp``).
    """
    sess = registry.require(network_id)
    sess.d.saveInputFile(output_path)
    return {"saved": True, "output_path": output_path}


# ---------------------------------------------------------------------------
# Demand modifications
# ---------------------------------------------------------------------------

def set_node_base_demand(
    network_id: str,
    node_id: str,
    demand: float,
    demand_category: int = 1,
) -> Dict[str, Any]:
    """
    Set the base demand for a junction node.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    node_id:
        Name/ID of the junction node.
    demand:
        New base demand value (in the network's flow units).
    demand_category:
        Demand category index (default 1 for the first/primary category).
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getNodeIndex(node_id)
    d.setNodeBaseDemands(idx, demand)
    return {"network_id": network_id, "node_id": node_id, "base_demand": demand}


def set_pattern(
    network_id: str,
    pattern_id: str,
    values: List[float],
) -> Dict[str, Any]:
    """
    Set (overwrite) all multiplier values for a named demand pattern.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pattern_id:
        Name of an existing pattern.
    values:
        List of multiplier values for consecutive pattern time steps.
    """
    sess = registry.require(network_id)
    d = sess.d
    pidx = d.getPatternIndex(pattern_id)
    d.setPattern(pidx, values)
    return {"network_id": network_id, "pattern_id": pattern_id, "values": values}


def add_pattern(
    network_id: str,
    pattern_id: str,
    values: List[float],
) -> Dict[str, Any]:
    """
    Add a new demand pattern to the network.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pattern_id:
        New unique pattern name.
    values:
        Multiplier values for the pattern.
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.addPattern(pattern_id, values)
    return {"network_id": network_id, "pattern_id": pattern_id, "pattern_index": to_python(idx)}


# ---------------------------------------------------------------------------
# Pipe modifications
# ---------------------------------------------------------------------------

def set_pipe_diameter(
    network_id: str,
    pipe_id: str,
    diameter: float,
) -> Dict[str, Any]:
    """
    Set the diameter of a pipe.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pipe_id:
        Pipe name/ID.
    diameter:
        New diameter (in the network's length units, typically mm or inches).
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getLinkIndex(pipe_id)
    d.setLinkDiameter(idx, diameter)
    return {"network_id": network_id, "pipe_id": pipe_id, "diameter": diameter}


def set_pipe_roughness(
    network_id: str,
    pipe_id: str,
    roughness: float,
) -> Dict[str, Any]:
    """
    Set the roughness coefficient of a pipe.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pipe_id:
        Pipe name/ID.
    roughness:
        Hazen-Williams C factor (or Darcy-Weisbach roughness height, depending
        on the head-loss formula set in the model).
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getLinkIndex(pipe_id)
    d.setLinkRoughnessCoeff(idx, roughness)
    return {"network_id": network_id, "pipe_id": pipe_id, "roughness": roughness}


def set_pipe_status(
    network_id: str,
    pipe_id: str,
    status: str,
) -> Dict[str, Any]:
    """
    Open or close a pipe.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pipe_id:
        Pipe name/ID.
    status:
        ``"OPEN"`` or ``"CLOSED"``.
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getLinkIndex(pipe_id)
    status_code = 1 if status.upper() == "OPEN" else 0
    d.setLinkInitialStatus(idx, status_code)
    return {"network_id": network_id, "pipe_id": pipe_id, "status": status.upper()}


def set_pipe_length(
    network_id: str,
    pipe_id: str,
    length: float,
) -> Dict[str, Any]:
    """
    Set the length of a pipe.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pipe_id:
        Pipe name/ID.
    length:
        New length in the network's length units (feet or metres).
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getLinkIndex(pipe_id)
    d.setLinkLength(idx, length)
    return {"network_id": network_id, "pipe_id": pipe_id, "length": length}


# ---------------------------------------------------------------------------
# Pump modifications
# ---------------------------------------------------------------------------

def set_pump_status(
    network_id: str,
    pump_id: str,
    status: str,
) -> Dict[str, Any]:
    """
    Open (start) or close (stop) a pump.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pump_id:
        Pump link name/ID.
    status:
        ``"OPEN"`` (running) or ``"CLOSED"`` (stopped).
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getLinkIndex(pump_id)
    status_code = 1 if status.upper() == "OPEN" else 0
    d.setLinkInitialStatus(idx, status_code)
    return {"network_id": network_id, "pump_id": pump_id, "status": status.upper()}


def set_pump_speed(
    network_id: str,
    pump_id: str,
    speed: float,
) -> Dict[str, Any]:
    """
    Set the relative speed setting of a pump (1.0 = design speed).

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pump_id:
        Pump link name/ID.
    speed:
        Speed ratio (e.g. 0.8 = 80 % of design speed, 1.0 = full speed).
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getLinkIndex(pump_id)
    d.setLinkInitialSetting(idx, speed)
    return {"network_id": network_id, "pump_id": pump_id, "speed": speed}


def set_pump_head_curve(
    network_id: str,
    pump_id: str,
    flow_values: List[float],
    head_values: List[float],
) -> Dict[str, Any]:
    """
    Set (replace) the head curve of a pump.

    A new curve is created and assigned to the pump.  The curve type is set
    to ``PUMP`` automatically.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    pump_id:
        Pump link name/ID.
    flow_values:
        X-axis (flow) values of the curve.
    head_values:
        Y-axis (head) values of the curve.
    """
    sess = registry.require(network_id)
    d = sess.d
    link_idx = d.getLinkIndex(pump_id)

    # getLinkPumpHeadCurveIndex() returns [pumpLinkIdx, curveIdx] pairs
    hc_pairs = d.getLinkPumpHeadCurveIndex()
    existing_curve_idx: Optional[int] = None
    for i in range(0, len(hc_pairs), 2):
        if int(hc_pairs[i]) == link_idx and i + 1 < len(hc_pairs):
            existing_curve_idx = int(hc_pairs[i + 1])
            break

    if existing_curve_idx and existing_curve_idx > 0:
        # Replace point by point: setCurveValue(curveIndex, pointNumber, (x, y))
        for pt_num, (x, y) in enumerate(zip(flow_values, head_values), start=1):
            d.setCurveValue(existing_curve_idx, pt_num, [x, y])
        curve_id = d.getCurveNameID(existing_curve_idx)
    else:
        # addCurve(curveID, curveXYvalues) where curveXYvalues is list of [x,y] pairs
        new_curve_id = f"{pump_id}_HCurve"
        xy_pairs = [[x, y] for x, y in zip(flow_values, head_values)]
        curve_idx = d.addCurve(new_curve_id, xy_pairs)
        d.setLinkPumpHCurve(link_idx, curve_idx)
        curve_id = new_curve_id

    return {
        "network_id": network_id,
        "pump_id": pump_id,
        "curve_id": curve_id,
        "flow_values": flow_values,
        "head_values": head_values,
    }


# ---------------------------------------------------------------------------
# Valve modifications
# ---------------------------------------------------------------------------

def set_valve_setting(
    network_id: str,
    valve_id: str,
    setting: float,
) -> Dict[str, Any]:
    """
    Set the initial setting of a valve (pressure setpoint, flow rate, etc.).

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    valve_id:
        Valve link name/ID.
    setting:
        New setting value.  Interpretation depends on valve type:
        PRV/PSV/PBV → pressure; FCV → flow; TCV → loss coefficient.
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getLinkIndex(valve_id)
    d.setLinkInitialSetting(idx, setting)
    return {"network_id": network_id, "valve_id": valve_id, "setting": setting}


def set_valve_status(
    network_id: str,
    valve_id: str,
    status: str,
) -> Dict[str, Any]:
    """
    Open or close a valve.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    valve_id:
        Valve link name/ID.
    status:
        ``"OPEN"`` or ``"CLOSED"``.
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getLinkIndex(valve_id)
    status_code = 1 if status.upper() == "OPEN" else 0
    d.setLinkInitialStatus(idx, status_code)
    return {"network_id": network_id, "valve_id": valve_id, "status": status.upper()}


# ---------------------------------------------------------------------------
# Tank modifications
# ---------------------------------------------------------------------------

def set_tank_parameters(
    network_id: str,
    tank_id: str,
    initial_level: Optional[float] = None,
    min_level: Optional[float] = None,
    max_level: Optional[float] = None,
    diameter: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Update one or more parameters of a tank node.

    Only the provided parameters are changed; others retain their current
    values.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    tank_id:
        Tank node name/ID.
    initial_level:
        Water level at the start of the simulation.
    min_level:
        Minimum operating level (below which the tank is considered empty).
    max_level:
        Maximum operating level (above which overflow occurs).
    diameter:
        Tank diameter (used for cylindrical volume calculations).
    """
    sess = registry.require(network_id)
    d = sess.d

    # Tank setters use 1-based index within the tank list (not global node index)
    tank_names = list(d.getNodeTankNameID())
    if tank_id not in tank_names:
        raise ValueError(f"No tank found with id={tank_id!r}. Tanks: {tank_names}")
    tank_idx = tank_names.index(tank_id) + 1  # 1-based

    # Apply changes in safe order: expand range before setting level
    if min_level is not None:
        d.setNodeTankMinimumWaterLevel(tank_idx, min_level)
    if max_level is not None:
        d.setNodeTankMaximumWaterLevel(tank_idx, max_level)
    if initial_level is not None:
        d.setNodeTankInitialLevel(tank_idx, initial_level)
    if diameter is not None:
        d.setNodeTankDiameter(tank_idx, diameter)

    return {
        "network_id": network_id,
        "tank_id": tank_id,
        "initial_level": initial_level,
        "min_level": min_level,
        "max_level": max_level,
        "diameter": diameter,
    }


# ---------------------------------------------------------------------------
# Reservoir modifications
# ---------------------------------------------------------------------------

def set_reservoir_head(
    network_id: str,
    reservoir_id: str,
    head: float,
) -> Dict[str, Any]:
    """
    Set the total head (water surface elevation) of a reservoir.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    reservoir_id:
        Reservoir node name/ID.
    head:
        Total head value in the network's pressure-head units.
    """
    sess = registry.require(network_id)
    d = sess.d
    idx = d.getNodeIndex(reservoir_id)
    d.setNodeElevations(idx, head)
    return {"network_id": network_id, "reservoir_id": reservoir_id, "head": head}


# ---------------------------------------------------------------------------
# Simulation time / option modifications
# ---------------------------------------------------------------------------

def set_simulation_duration(
    network_id: str,
    duration_s: int,
) -> Dict[str, Any]:
    """
    Set the total simulation duration.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    duration_s:
        Simulation duration in seconds (e.g. 86400 = 24 hours).
    """
    sess = registry.require(network_id)
    sess.d.setTimeSimulationDuration(duration_s)
    return {"network_id": network_id, "simulation_duration_s": duration_s}


def set_hydraulic_timestep(
    network_id: str,
    timestep_s: int,
) -> Dict[str, Any]:
    """
    Set the hydraulic time step.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    timestep_s:
        Hydraulic time step in seconds.
    """
    sess = registry.require(network_id)
    sess.d.setTimeHydraulicStep(timestep_s)
    return {"network_id": network_id, "hydraulic_timestep_s": timestep_s}


def set_quality_timestep(
    network_id: str,
    timestep_s: int,
) -> Dict[str, Any]:
    """
    Set the water-quality simulation time step.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    timestep_s:
        Quality time step in seconds.
    """
    sess = registry.require(network_id)
    sess.d.setTimeQualityStep(timestep_s)
    return {"network_id": network_id, "quality_timestep_s": timestep_s}


def set_quality_type(
    network_id: str,
    quality_type: str,
    tracer_node: Optional[str] = None,
    chemical_name: Optional[str] = None,
    units: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Set the water-quality analysis type.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    quality_type:
        One of ``"NONE"``, ``"AGE"``, ``"TRACE"``, or ``"CHEM"``.
    tracer_node:
        Node ID used as the source for trace analysis (required when
        ``quality_type="TRACE"``).
    chemical_name:
        Chemical species name (used when ``quality_type="CHEM"``).
    units:
        Concentration units string (e.g. ``"mg/L"``).
    """
    sess = registry.require(network_id)
    d = sess.d

    qt = quality_type.upper()
    args: list = [qt]
    if qt == "TRACE" and tracer_node:
        args.append(tracer_node)
    if chemical_name:
        args.append(chemical_name)
    if units:
        args.append(units)
    d.setQualityType(*args)

    return {
        "network_id": network_id,
        "quality_type": qt,
        "tracer_node": tracer_node,
        "chemical_name": chemical_name,
        "units": units,
    }


# ---------------------------------------------------------------------------
# Control modifications
# ---------------------------------------------------------------------------

def add_control(
    network_id: str,
    control_string: str,
) -> Dict[str, Any]:
    """
    Add a new simple control rule to the network.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    control_string:
        EPANET control syntax, e.g.
        ``"LINK P1 CLOSED IF NODE T1 ABOVE 20"``
        ``"LINK P1 OPEN IF NODE J2 BELOW 10"``
        ``"LINK P1 1.5 AT TIME 16:00"``
    """
    sess = registry.require(network_id)
    idx = sess.d.addControls(control_string)
    return {"network_id": network_id, "control_string": control_string, "control_index": to_python(idx)}


def delete_control(
    network_id: str,
    control_index: int,
) -> Dict[str, Any]:
    """
    Delete a simple control by its 1-based index.

    Parameters
    ----------
    network_id:
        Id of a previously loaded network.
    control_index:
        The 1-based control index (use ``get_controls`` to list them).
    """
    sess = registry.require(network_id)
    sess.d.deleteControls(control_index)
    return {"network_id": network_id, "deleted_control_index": control_index}
