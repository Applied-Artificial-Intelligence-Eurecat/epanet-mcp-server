"""
Tools for loading and inspecting EPANET network models.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import os

from epyt import epanet

from epanet_mcp.session import NetworkSession, registry
from epanet_mcp.utils import safe_list, to_python, resolve_network_path

# ---------------------------------------------------------------------------
# Load / unload
# ---------------------------------------------------------------------------


def load_network(path: str, network_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Load an EPANET .inp file into a named session.

    Parameters
    ----------
    path:
        Absolute path to a .inp file **or** a bare name like ``"Net1.inp"``
        which will be searched in ePyT's bundled networks directory.
    network_id:
        Optional human-readable identifier.  Defaults to the file basename.

    Returns
    -------
    dict with ``network_id``, ``path``, and a brief network summary.
    """
    resolved = resolve_network_path(path)
    if not os.path.exists(resolved):
        raise FileNotFoundError(f"Network file not found: {resolved!r}")

    nid = network_id or os.path.splitext(os.path.basename(resolved))[0]

    # unload any existing session with the same id
    registry.remove(nid)

    # ph=True enables the EPANET 2.2 project-handle API, which supports
    # multiple concurrent network instances in the same process.
    d = epanet(resolved, display_msg=False, ph=True)
    sess = NetworkSession(network_id=nid, path=resolved, d=d)
    registry.add(sess)

    return {
        "network_id": nid,
        "path": resolved,
        "summary": _network_summary(d),
    }


def unload_network(network_id: str) -> Dict[str, Any]:
    """
    Unload a previously loaded network, freeing its resources.

    Parameters
    ----------
    network_id:
        The id returned by ``load_network``.
    """
    removed = registry.remove(network_id)
    return {"unloaded": removed, "network_id": network_id}


def list_networks() -> Dict[str, Any]:
    """Return the ids of all currently loaded networks."""
    return {"loaded_networks": registry.list_ids()}


def list_bundled_networks() -> Dict[str, Any]:
    """List every .inp file bundled with ePyT (available for ``load_network``)."""
    import epyt

    networks_dir = os.path.join(os.path.dirname(epyt.__file__), "networks")
    results = []
    for root, _dirs, files in os.walk(networks_dir):
        for f in files:
            if f.lower().endswith(".inp"):
                results.append(os.path.relpath(os.path.join(root, f), networks_dir))
    return {"bundled_networks": sorted(results)}


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------


def get_network_summary(network_id: str) -> Dict[str, Any]:
    """
    High-level summary: node/link counts, flow units, simulation options.
    """
    sess = registry.require(network_id)
    d = sess.d
    return _network_summary(d)


def get_nodes(network_id: str) -> Dict[str, Any]:
    """
    Return all nodes (junctions, tanks, reservoirs) with their attributes.
    """
    sess = registry.require(network_id)
    d = sess.d

    node_ids = safe_list(d.getNodeNameID())
    elevations = safe_list(d.getNodeElevations())
    node_types = safe_list(d.getNodeType())
    base_demands = safe_list(d.getNodeBaseDemands()[1])  # index 1 = first category

    nodes = []
    for i, nid in enumerate(node_ids):
        node = {
            "id": nid,
            "index": i + 1,
            "type": node_types[i] if i < len(node_types) else None,
            "elevation": elevations[i] if i < len(elevations) else None,
            "base_demand": base_demands[i] if i < len(base_demands) else None,
        }
        nodes.append(node)

    # extra tank data
    tank_ids = safe_list(d.getNodeTankNameID())
    if tank_ids:
        tank_data = _tank_data(d, tank_ids)
        for n in nodes:
            if n["id"] in tank_data:
                n.update(tank_data[n["id"]])

    # extra reservoir data
    res_ids = safe_list(d.getNodeReservoirNameID())
    for n in nodes:
        if n["id"] in res_ids:
            n["type"] = "Reservoir"

    return {"nodes": nodes}


def get_links(network_id: str) -> Dict[str, Any]:
    """
    Return all links (pipes, pumps, valves) with their attributes.
    """
    sess = registry.require(network_id)
    d = sess.d

    link_ids = safe_list(d.getLinkNameID())
    link_types = safe_list(d.getLinkType())
    diameters = safe_list(d.getLinkDiameter())
    lengths = safe_list(d.getLinkLength())
    roughness = safe_list(d.getLinkRoughnessCoeff())
    minor_loss = safe_list(d.getLinkMinorLossCoeff())
    node_pairs = d.getLinkNodesIndex()
    node_names = safe_list(d.getNodeNameID())

    links = []
    for i, lid in enumerate(link_ids):
        from_idx, to_idx = node_pairs[i]
        link = {
            "id": lid,
            "index": i + 1,
            "type": link_types[i] if i < len(link_types) else None,
            "from_node": node_names[from_idx - 1] if from_idx > 0 else None,
            "to_node": node_names[to_idx - 1] if to_idx > 0 else None,
            "diameter": diameters[i] if i < len(diameters) else None,
            "length": lengths[i] if i < len(lengths) else None,
            "roughness": roughness[i] if i < len(roughness) else None,
            "minor_loss_coeff": minor_loss[i] if i < len(minor_loss) else None,
        }
        links.append(link)

    return {"links": links}


def get_patterns(network_id: str) -> Dict[str, Any]:
    """Return all demand/time patterns defined in the network."""
    sess = registry.require(network_id)
    d = sess.d
    pattern_ids = safe_list(d.getPatternNameID())
    patterns = []
    for i, pid in enumerate(pattern_ids):
        idx = i + 1
        n_steps = int(d.getPatternLengths(idx))
        # getPatternValue takes a single integer step (1-based), not a list
        values = [float(d.getPatternValue(idx, step)) for step in range(1, n_steps + 1)]
        patterns.append({"id": pid, "index": idx, "values": values})
    return {"patterns": patterns}


def get_controls(network_id: str) -> Dict[str, Any]:
    """Return all simple controls defined in the network."""
    sess = registry.require(network_id)
    d = sess.d
    count = d.getControlCount()
    controls = []
    for i in range(1, count + 1):
        ctrl = d.getControls(i)
        controls.append(
            {
                "index": i,
                "control": ctrl.Control if hasattr(ctrl, "Control") else str(ctrl),
            }
        )
    return {"controls": controls}


def get_curves(network_id: str) -> Dict[str, Any]:
    """Return all curves (pump head, efficiency, volume, etc.)."""
    sess = registry.require(network_id)
    d = sess.d
    info = d.getCurvesInfo()
    curves = []
    curve_ids = safe_list(info.CurveNameID)
    # getCurveType() returns a list of type strings (same order as curves)
    curve_types = safe_list(d.getCurveType()) if curve_ids else []
    curve_x = info.CurveXvalue
    curve_y = info.CurveYvalue
    for i, cid in enumerate(curve_ids):
        curves.append(
            {
                "id": cid,
                "index": i + 1,
                "type": curve_types[i] if i < len(curve_types) else None,
                "x_values": safe_list(curve_x[i]) if i < len(curve_x) else [],
                "y_values": safe_list(curve_y[i]) if i < len(curve_y) else [],
            }
        )
    return {"curves": curves}


def get_options(network_id: str) -> Dict[str, Any]:
    """Return simulation options (timesteps, units, quality settings, etc.)."""
    sess = registry.require(network_id)
    d = sess.d
    return {
        "flow_units": d.getFlowUnits(),
        "hydraulic_timestep_s": to_python(d.getTimeHydraulicStep()),
        "quality_timestep_s": to_python(d.getTimeQualityStep()),
        "simulation_duration_s": to_python(d.getTimeSimulationDuration()),
        "pattern_timestep_s": to_python(d.getTimePatternStep()),
        "reporting_step_s": to_python(d.getTimeReportingStep()),
        "quality_type": d.getQualityInfo().QualityType,
        "head_loss_formula": str(d.getOptionsHeadLossFormula()),
        "demand_model": str(d.getDemandModel().DemandModelType),
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _network_summary(d: epanet) -> Dict[str, Any]:
    counts = d.getCounts()
    return {
        "nodes": {
            "total": to_python(counts.Nodes),
            "junctions": to_python(counts.Junctions),
            "tanks": to_python(counts.Tanks),
            "reservoirs": to_python(counts.Reservoirs),
        },
        "links": {
            "total": to_python(counts.Links),
            "pipes": to_python(counts.Pipes),
            "pumps": to_python(counts.Pumps),
            "valves": to_python(counts.Valves),
        },
        "patterns": to_python(counts.Patterns),
        "curves": to_python(counts.Curves),
        "simple_controls": to_python(counts.SimpleControls),
        "rule_based_controls": to_python(counts.RuleBasedControls),
        "flow_units": d.getFlowUnits(),
        "simulation_duration_s": to_python(d.getTimeSimulationDuration()),
        "hydraulic_timestep_s": to_python(d.getTimeHydraulicStep()),
    }


def _tank_data(d: epanet, tank_ids: list) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    min_lvls = safe_list(d.getNodeTankMinimumWaterLevel())
    max_lvls = safe_list(d.getNodeTankMaximumWaterLevel())
    init_lvls = safe_list(d.getNodeTankInitialLevel())
    diameters = safe_list(d.getNodeTankDiameter())
    for i, tid in enumerate(tank_ids):
        result[tid] = {
            "type": "Tank",
            "min_level": min_lvls[i] if i < len(min_lvls) else None,
            "max_level": max_lvls[i] if i < len(max_lvls) else None,
            "initial_level": init_lvls[i] if i < len(init_lvls) else None,
            "diameter": diameters[i] if i < len(diameters) else None,
        }
    return result
