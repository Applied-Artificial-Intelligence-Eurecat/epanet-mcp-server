"""
EPANET MCP Server
=================

Exposes EPANET water-distribution network modelling capabilities as MCP tools,
powered by the ePyT Python toolkit.

Start with stdio transport (default for Claude Desktop / CLI):

    python -m epanet_mcp.server
    # or
    epanet-mcp-server

Start with SSE transport (for HTTP clients):

    python -m epanet_mcp.server --transport sse --port 8000
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from epanet_mcp.tools import inspection, simulation, modification, scenarios

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "EPANET MCP Server",
    instructions=(
        "Water distribution network simulation via ePyT/EPANET.  "
        "Load a .inp model with `load_network`, inspect its topology, run "
        "hydraulic / water-quality simulations, modify parameters, and "
        "generate what-if scenarios."
    ),
)

# ===========================================================================
# INSPECTION TOOLS
# ===========================================================================


@mcp.tool()
def load_network(
    path: str,
    network_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load an EPANET .inp file into a named session.

    Args:
        path: Absolute file path, relative path, or bare filename
              (e.g. ``"Net1.inp"``) searched in ePyT's bundled networks.
        network_id: Optional human-readable session identifier.
                    Defaults to the file's base name without extension.

    Returns:
        ``network_id``, ``path``, and a network summary (node/link counts,
        flow units, simulation duration).
    """
    return inspection.load_network(path, network_id)


@mcp.tool()
def unload_network(network_id: str) -> Dict[str, Any]:
    """
    Unload a previously loaded network and free its resources.

    Args:
        network_id: The session id returned by ``load_network``.
    """
    return inspection.unload_network(network_id)


@mcp.tool()
def list_networks() -> Dict[str, Any]:
    """
    Return the ids of all currently loaded networks.
    """
    return inspection.list_networks()


@mcp.tool()
def list_bundled_networks() -> Dict[str, Any]:
    """
    List every .inp example file bundled with ePyT (usable with load_network).
    """
    return inspection.list_bundled_networks()


@mcp.tool()
def get_network_summary(network_id: str) -> Dict[str, Any]:
    """
    Return a high-level summary of a loaded network.

    Includes node/link counts, flow units, simulation duration and
    hydraulic timestep.

    Args:
        network_id: Session id of the network to inspect.
    """
    return inspection.get_network_summary(network_id)


@mcp.tool()
def get_nodes(network_id: str) -> Dict[str, Any]:
    """
    Return all nodes (junctions, tanks, reservoirs) with their attributes.

    Attributes include elevation, base demand, and type.  Tanks also include
    min/max/initial water levels and diameter.

    Args:
        network_id: Session id of the network to inspect.
    """
    return inspection.get_nodes(network_id)


@mcp.tool()
def get_links(network_id: str) -> Dict[str, Any]:
    """
    Return all links (pipes, pumps, valves) with their attributes.

    Attributes include type, connected nodes, diameter, length, roughness
    coefficient, and minor loss coefficient.

    Args:
        network_id: Session id of the network to inspect.
    """
    return inspection.get_links(network_id)


@mcp.tool()
def get_patterns(network_id: str) -> Dict[str, Any]:
    """
    Return all demand / operational patterns defined in the network.

    Args:
        network_id: Session id of the network to inspect.
    """
    return inspection.get_patterns(network_id)


@mcp.tool()
def get_controls(network_id: str) -> Dict[str, Any]:
    """
    Return all simple controls defined in the network.

    Args:
        network_id: Session id of the network to inspect.
    """
    return inspection.get_controls(network_id)


@mcp.tool()
def get_curves(network_id: str) -> Dict[str, Any]:
    """
    Return all curves (pump head, efficiency, volume, valve) in the network.

    Args:
        network_id: Session id of the network to inspect.
    """
    return inspection.get_curves(network_id)


@mcp.tool()
def get_options(network_id: str) -> Dict[str, Any]:
    """
    Return simulation options: timesteps, units, quality settings, head-loss
    formula, and demand model.

    Args:
        network_id: Session id of the network to inspect.
    """
    return inspection.get_options(network_id)


# ===========================================================================
# SIMULATION TOOLS
# ===========================================================================


@mcp.tool()
def run_hydraulic_simulation(network_id: str) -> Dict[str, Any]:
    """
    Run a full hydraulic simulation and return time-series results.

    Returns pressures, demands, heads, flows, velocities, head-losses and
    link statuses at every reporting time step.

    Args:
        network_id: Session id of the network to simulate.
    """
    return simulation.run_hydraulic_simulation(network_id)


@mcp.tool()
def run_quality_simulation(network_id: str) -> Dict[str, Any]:
    """
    Run a full water-quality simulation and return time-series results.

    Includes node/link quality concentrations plus all hydraulic results.
    Configure the quality type first with ``set_quality_type``.

    Args:
        network_id: Session id of the network to simulate.
    """
    return simulation.run_quality_simulation(network_id)


@mcp.tool()
def run_full_simulation(network_id: str) -> Dict[str, Any]:
    """
    Run both hydraulic and water-quality simulations and return combined
    time-series results (pressures, flows, quality, reaction rates, etc.).

    Args:
        network_id: Session id of the network to simulate.
    """
    return simulation.run_full_simulation(network_id)


@mcp.tool()
def get_pressure_at_time(network_id: str, time_s: int) -> Dict[str, Any]:
    """
    Return node pressures at (or nearest to) a specific simulation time.

    Args:
        network_id: Session id of the network.
        time_s: Simulation time in seconds (e.g. 3600 = 1 hour).
    """
    return simulation.get_pressure_at_time(network_id, time_s)


@mcp.tool()
def get_flow_at_time(network_id: str, time_s: int) -> Dict[str, Any]:
    """
    Return link flows at (or nearest to) a specific simulation time.

    Args:
        network_id: Session id of the network.
        time_s: Simulation time in seconds.
    """
    return simulation.get_flow_at_time(network_id, time_s)


# ===========================================================================
# MODIFICATION TOOLS
# ===========================================================================


@mcp.tool()
def save_network(network_id: str, output_path: str) -> Dict[str, Any]:
    """
    Save the current (possibly modified) network to a new .inp file.

    Args:
        network_id: Session id of the network to save.
        output_path: Destination file path (should end in ``.inp``).
    """
    return modification.save_network(network_id, output_path)


@mcp.tool()
def set_node_base_demand(
    network_id: str,
    node_id: str,
    demand: float,
    demand_category: int = 1,
) -> Dict[str, Any]:
    """
    Set the base demand for a junction node.

    Args:
        network_id: Session id.
        node_id: Junction node name/ID.
        demand: New base demand in the network's flow units.
        demand_category: Demand category index (default 1).
    """
    return modification.set_node_base_demand(network_id, node_id, demand, demand_category)


@mcp.tool()
def set_pattern(
    network_id: str,
    pattern_id: str,
    values: List[float],
) -> Dict[str, Any]:
    """
    Overwrite all multiplier values for a named demand pattern.

    Args:
        network_id: Session id.
        pattern_id: Name of an existing pattern.
        values: New list of multiplier values.
    """
    return modification.set_pattern(network_id, pattern_id, values)


@mcp.tool()
def add_pattern(
    network_id: str,
    pattern_id: str,
    values: List[float],
) -> Dict[str, Any]:
    """
    Add a new demand / operational pattern to the network.

    Args:
        network_id: Session id.
        pattern_id: Unique name for the new pattern.
        values: Multiplier values for consecutive pattern time steps.
    """
    return modification.add_pattern(network_id, pattern_id, values)


@mcp.tool()
def set_pipe_diameter(
    network_id: str,
    pipe_id: str,
    diameter: float,
) -> Dict[str, Any]:
    """
    Set the diameter of a pipe.

    Args:
        network_id: Session id.
        pipe_id: Pipe name/ID.
        diameter: New diameter in the network's length units (mm or inches).
    """
    return modification.set_pipe_diameter(network_id, pipe_id, diameter)


@mcp.tool()
def set_pipe_roughness(
    network_id: str,
    pipe_id: str,
    roughness: float,
) -> Dict[str, Any]:
    """
    Set the roughness coefficient of a pipe.

    Args:
        network_id: Session id.
        pipe_id: Pipe name/ID.
        roughness: Hazen-Williams C factor (or Darcy-Weisbach roughness height).
    """
    return modification.set_pipe_roughness(network_id, pipe_id, roughness)


@mcp.tool()
def set_pipe_status(
    network_id: str,
    pipe_id: str,
    status: str,
) -> Dict[str, Any]:
    """
    Open or close a pipe.

    Args:
        network_id: Session id.
        pipe_id: Pipe name/ID.
        status: ``"OPEN"`` or ``"CLOSED"``.
    """
    return modification.set_pipe_status(network_id, pipe_id, status)


@mcp.tool()
def set_pipe_length(
    network_id: str,
    pipe_id: str,
    length: float,
) -> Dict[str, Any]:
    """
    Set the length of a pipe.

    Args:
        network_id: Session id.
        pipe_id: Pipe name/ID.
        length: New length in the network's length units (feet or metres).
    """
    return modification.set_pipe_length(network_id, pipe_id, length)


@mcp.tool()
def set_pump_status(
    network_id: str,
    pump_id: str,
    status: str,
) -> Dict[str, Any]:
    """
    Start or stop a pump.

    Args:
        network_id: Session id.
        pump_id: Pump link name/ID.
        status: ``"OPEN"`` (running) or ``"CLOSED"`` (stopped).
    """
    return modification.set_pump_status(network_id, pump_id, status)


@mcp.tool()
def set_pump_speed(
    network_id: str,
    pump_id: str,
    speed: float,
) -> Dict[str, Any]:
    """
    Set the relative speed setting of a pump.

    Args:
        network_id: Session id.
        pump_id: Pump link name/ID.
        speed: Speed ratio (1.0 = design speed, 0.5 = half speed).
    """
    return modification.set_pump_speed(network_id, pump_id, speed)


@mcp.tool()
def set_pump_head_curve(
    network_id: str,
    pump_id: str,
    flow_values: List[float],
    head_values: List[float],
) -> Dict[str, Any]:
    """
    Set (replace) the head-flow curve of a pump.

    Args:
        network_id: Session id.
        pump_id: Pump link name/ID.
        flow_values: X-axis (flow) values.
        head_values: Y-axis (head) values.
    """
    return modification.set_pump_head_curve(network_id, pump_id, flow_values, head_values)


@mcp.tool()
def set_valve_setting(
    network_id: str,
    valve_id: str,
    setting: float,
) -> Dict[str, Any]:
    """
    Set the initial setting of a valve.

    PRV/PSV/PBV → pressure setpoint; FCV → flow rate; TCV → loss coefficient.

    Args:
        network_id: Session id.
        valve_id: Valve link name/ID.
        setting: New setting value.
    """
    return modification.set_valve_setting(network_id, valve_id, setting)


@mcp.tool()
def set_valve_status(
    network_id: str,
    valve_id: str,
    status: str,
) -> Dict[str, Any]:
    """
    Open or close a valve.

    Args:
        network_id: Session id.
        valve_id: Valve link name/ID.
        status: ``"OPEN"`` or ``"CLOSED"``.
    """
    return modification.set_valve_status(network_id, valve_id, status)


@mcp.tool()
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

    Only provided parameters are changed; others retain their current values.

    Args:
        network_id: Session id.
        tank_id: Tank node name/ID.
        initial_level: Water level at simulation start.
        min_level: Minimum operating level.
        max_level: Maximum operating level.
        diameter: Tank diameter.
    """
    return modification.set_tank_parameters(
        network_id, tank_id, initial_level, min_level, max_level, diameter
    )


@mcp.tool()
def set_reservoir_head(
    network_id: str,
    reservoir_id: str,
    head: float,
) -> Dict[str, Any]:
    """
    Set the total head (water-surface elevation) of a reservoir.

    Args:
        network_id: Session id.
        reservoir_id: Reservoir node name/ID.
        head: Total head value in the network's pressure-head units.
    """
    return modification.set_reservoir_head(network_id, reservoir_id, head)


@mcp.tool()
def set_simulation_duration(network_id: str, duration_s: int) -> Dict[str, Any]:
    """
    Set the total simulation duration.

    Args:
        network_id: Session id.
        duration_s: Duration in seconds (e.g. 86400 = 24 h).
    """
    return modification.set_simulation_duration(network_id, duration_s)


@mcp.tool()
def set_hydraulic_timestep(network_id: str, timestep_s: int) -> Dict[str, Any]:
    """
    Set the hydraulic time step.

    Args:
        network_id: Session id.
        timestep_s: Hydraulic time step in seconds.
    """
    return modification.set_hydraulic_timestep(network_id, timestep_s)


@mcp.tool()
def set_quality_timestep(network_id: str, timestep_s: int) -> Dict[str, Any]:
    """
    Set the water-quality simulation time step.

    Args:
        network_id: Session id.
        timestep_s: Quality time step in seconds.
    """
    return modification.set_quality_timestep(network_id, timestep_s)


@mcp.tool()
def set_quality_type(
    network_id: str,
    quality_type: str,
    tracer_node: Optional[str] = None,
    chemical_name: Optional[str] = None,
    units: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Set the water-quality analysis type.

    Args:
        network_id: Session id.
        quality_type: One of ``"NONE"``, ``"AGE"``, ``"TRACE"``, or ``"CHEM"``.
        tracer_node: Source node for ``TRACE`` analysis.
        chemical_name: Species name for ``CHEM`` analysis.
        units: Concentration units (e.g. ``"mg/L"``).
    """
    return modification.set_quality_type(
        network_id, quality_type, tracer_node, chemical_name, units
    )


@mcp.tool()
def add_control(network_id: str, control_string: str) -> Dict[str, Any]:
    """
    Add a new simple control rule.

    Example control strings::

        "LINK P1 CLOSED IF NODE T1 ABOVE 20"
        "LINK P1 OPEN IF NODE J2 BELOW 10"
        "LINK Pump9 1.5 AT TIME 16:00"

    Args:
        network_id: Session id.
        control_string: EPANET simple-control syntax string.
    """
    return modification.add_control(network_id, control_string)


@mcp.tool()
def delete_control(network_id: str, control_index: int) -> Dict[str, Any]:
    """
    Delete a simple control by its 1-based index.

    Args:
        network_id: Session id.
        control_index: 1-based index (use ``get_controls`` to list them).
    """
    return modification.delete_control(network_id, control_index)


# ===========================================================================
# SCENARIO TOOLS
# ===========================================================================


@mcp.tool()
def create_demand_perturbation(
    network_id: str,
    node_demands: Dict[str, float],
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Apply base-demand multipliers to a set of nodes and optionally simulate.

    A clone of the source network is created; the original is unchanged.

    Args:
        network_id: Source network id.
        node_demands: ``{node_id: multiplier}`` — e.g. ``{"J1": 2.0}``
                      doubles demand at J1.
        scenario_id: Id for the cloned scenario session (auto-generated if
                     omitted).
        run_simulation: Run a full simulation after applying changes.
    """
    return scenarios.create_demand_perturbation(
        network_id, node_demands, scenario_id, run_simulation
    )


@mcp.tool()
def create_leakage_event(
    network_id: str,
    pipe_id: str,
    leak_fraction: float,
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Simulate a pipe burst by adding a leakage emitter at the pipe midpoint.

    A clone of the source network is created; the original is unchanged.
    The burst pipe is split into two halves and a midpoint junction node with
    an emitter is added.

    Args:
        network_id: Source network id.
        pipe_id: Id of the pipe that bursts.
        leak_fraction: Fraction of flow that leaks (0.0–1.0).
        scenario_id: Id for the cloned scenario session.
        run_simulation: Run a full simulation after applying changes.
    """
    return scenarios.create_leakage_event(
        network_id, pipe_id, leak_fraction, scenario_id, run_simulation
    )


@mcp.tool()
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
    Inject a contaminant at a node for a specified time window and simulate.

    A clone of the source network is created.  Quality type is set to CHEM
    automatically.

    Args:
        network_id: Source network id.
        source_node_id: Node where the contaminant is introduced.
        concentration: Concentration in mg/L (or model quality units).
        start_time_s: Injection start time in seconds.
        end_time_s: Injection end time in seconds.
        source_type: ``"CONCEN"``, ``"MASS"``, ``"FLOWPACED"``, or
                     ``"SETPOINT"``.
        scenario_id: Id for the cloned scenario session.
        run_simulation: Run a full simulation after applying changes.
    """
    return scenarios.create_contamination_event(
        network_id,
        source_node_id,
        concentration,
        start_time_s,
        end_time_s,
        source_type,
        scenario_id,
        run_simulation,
    )


@mcp.tool()
def create_pressure_change_scenario(
    network_id: str,
    reservoir_heads: Dict[str, float],
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Study pressure changes by modifying reservoir heads.

    A clone of the source network is created; the original is unchanged.

    Args:
        network_id: Source network id.
        reservoir_heads: ``{reservoir_id: new_head}`` — e.g.
                         ``{"Reservoir1": 120.0}``.
        scenario_id: Id for the cloned scenario session.
        run_simulation: Run a full simulation after applying changes.
    """
    return scenarios.create_pressure_change_scenario(
        network_id, reservoir_heads, scenario_id, run_simulation
    )


@mcp.tool()
def create_pump_control_scenario(
    network_id: str,
    pump_schedule: Dict[str, List[str]],
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Apply a time-based pump on/off or speed schedule and simulate.

    A clone of the source network is created; the original is unchanged.

    Each pump entry maps to a list of EPANET simple-control strings::

        {
            "Pump9": [
                "LINK Pump9 1.0 AT TIME 06:00",
                "LINK Pump9 CLOSED AT TIME 22:00"
            ]
        }

    Args:
        network_id: Source network id.
        pump_schedule: ``{pump_id: [control_string, ...]}`` schedule.
        scenario_id: Id for the cloned scenario session.
        run_simulation: Run a full simulation after applying changes.
    """
    return scenarios.create_pump_control_scenario(
        network_id, pump_schedule, scenario_id, run_simulation
    )


@mcp.tool()
def create_valve_control_scenario(
    network_id: str,
    valve_settings: Dict[str, float],
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Apply static valve-setting changes and simulate.

    A clone of the source network is created; the original is unchanged.

    Args:
        network_id: Source network id.
        valve_settings: ``{valve_id: new_setting}`` map.
        scenario_id: Id for the cloned scenario session.
        run_simulation: Run a full simulation after applying changes.
    """
    return scenarios.create_valve_control_scenario(
        network_id, valve_settings, scenario_id, run_simulation
    )


@mcp.tool()
def create_multi_failure_scenario(
    network_id: str,
    failed_pipes: Optional[List[str]] = None,
    failed_pumps: Optional[List[str]] = None,
    scenario_id: Optional[str] = None,
    run_simulation: bool = True,
) -> Dict[str, Any]:
    """
    Simulate simultaneous pipe and/or pump failures (closure).

    A clone of the source network is created; the original is unchanged.

    Args:
        network_id: Source network id.
        failed_pipes: List of pipe ids to close.
        failed_pumps: List of pump ids to close.
        scenario_id: Id for the cloned scenario session.
        run_simulation: Run a full simulation after applying changes.
    """
    return scenarios.create_multi_failure_scenario(
        network_id, failed_pipes, failed_pumps, scenario_id, run_simulation
    )


# ===========================================================================
# Entry point
# ===========================================================================


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="EPANET MCP Server via ePyT")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for SSE transport (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
