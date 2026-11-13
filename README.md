# EPANET MCP Server

[![Linter](https://github.com/Applied-Artificial-Intelligence-Eurecat/epanet-mcp-server/actions/workflows/linter.yml/badge.svg?branch=main)](https://github.com/Applied-Artificial-Intelligence-Eurecat/epanet-mcp-server/actions/workflows/linter.yml)
[![Pytest](https://github.com/Applied-Artificial-Intelligence-Eurecat/epanet-mcp-server/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/Applied-Artificial-Intelligence-Eurecat/epanet-mcp-server/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/epanet-mcp-server.svg?label=PyPI)](https://pypi.org/project/epanet-mcp-server/)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-listed-blue.svg)](https://registry.modelcontextprotocol.io/?q=io.github.Applied-Artificial-Intelligence-Eurecat%2Fepanet-mcp-server)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that
exposes EPANET water-distribution network modelling capabilities through
[ePyT](https://github.com/KIOS-Research/EPyT) - the EPANET Python Toolkit.

Any MCP-compatible LLM can load water network models, run
simulations, modify parameters, and generate complex what-if scenarios through
natural language.

---

## Features

| Category | Tools |
|---|---|
| **Load & Inspect** | `load_network`, `unload_network`, `list_networks`, `list_bundled_networks`, `get_network_summary`, `get_nodes`, `get_links`, `get_patterns`, `get_controls`, `get_curves`, `get_options` |
| **Simulate** | `run_hydraulic_simulation`, `run_quality_simulation`, `run_full_simulation`, `get_pressure_at_time`, `get_flow_at_time` |
| **Modify** | `set_node_base_demand`, `set_pattern`, `add_pattern`, `set_pipe_diameter`, `set_pipe_roughness`, `set_pipe_status`, `set_pipe_length`, `set_pump_status`, `set_pump_speed`, `set_pump_head_curve`, `set_valve_setting`, `set_valve_status`, `set_tank_parameters`, `set_reservoir_head`, `set_simulation_duration`, `set_hydraulic_timestep`, `set_pattern_timestep`, `set_quality_timestep`, `set_quality_type`, `add_control`, `delete_control`, `save_network` |
| **Scenarios** | `create_demand_perturbation`, `create_leakage_event`, `create_contamination_event`, `create_pressure_change_scenario`, `create_pump_control_scenario`, `create_valve_control_scenario`, `create_multi_failure_scenario` |

---

## Requirements

- Python ≥ 3.10
- [ePyT](https://pypi.org/project/epyt/) ≥ 2.0
- [mcp](https://pypi.org/project/mcp/) ≥ 1.0

```bash
pip install epyt mcp
```

---

## Installation

```bash
git clone https://github.com/Applied-Artificial-Intelligence-Eurecat/epanet-mcp-server.git
cd epanet-mcp-server
pip install -e .
```

---

## Running the server

### stdio (for Claude Desktop / Claude Code)

```bash
epanet-mcp-server
# or
python -m epanet_mcp.server
```

### SSE / HTTP

```bash
epanet-mcp-server --transport sse --port 8000
```

---

## Claude Desktop configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or the equivalent on your platform:

```json
{
  "mcpServers": {
    "epanet": {
      "command": "epanet-mcp-server",
      "args": []
    }
  }
}
```

If not on `PATH`:

```json
{
  "mcpServers": {
    "epanet": {
      "command": "python",
      "args": ["-m", "epanet_mcp.server"],
      "cwd": "/path/to/epanet-mcp-server/src"
    }
  }
}
```

---

## Claude Code (`.mcp.json`)

Place this in the root of your project or `~/.claude/`:

```json
{
  "mcpServers": {
    "epanet": {
      "command": "epanet-mcp-server",
      "args": []
    }
  }
}
```

---

## Example interactions

Once the server is connected, you can ask things like:

> **"Load Net1.inp and show me a summary of the network."**

> **"Run a full simulation and tell me which node has the lowest pressure at hour 12."**

> **"Double the base demand at junction 11 and re-run the simulation. How does pressure change?"**

> **"Simulate a burst on pipe 10 with a 20% leakage fraction."**

> **"Inject 10 mg/L of chlorine at node 11 between hours 1 and 3 and show me the contamination spread."**

> **"What happens to pressures if the reservoir head drops from 150 m to 120 m?"**

> **"Schedule Pump 9 to start at 06:00 and stop at 22:00."**

> **"Close pipes 10 and 11 and the pump simultaneously. Where are service disruptions?"**

---

## Architecture

```
src/epanet_mcp/
├── server.py          # FastMCP server – tool registration + entry point
├── session.py         # Session leases, lifecycle states, registry ownership
├── utils.py           # numpy → Python serialisation helpers
├── application/
│   └── scenario_service.py # Transactional scenario publication
├── domain/
│   ├── scenario.py    # Scenario lineage and change manifests
│   └── validation.py  # Shared physical and identifier validation
├── engine/
│   └── runner.py      # Isolated, serialized EPANET solver workspaces
└── tools/
    ├── inspection.py  # load / inspect network models
    ├── simulation.py  # run hydraulic & quality simulations
    ├── modification.py# in-memory parameter changes
    └── scenarios.py   # what-if scenario generators (clone + modify + run)
```

**Session model**: Each loaded network lives in a named session. Every ePyT
operation holds an exclusive lease on that session, so unload and replacement
wait for in-flight work before disposing the project handle. Loading a network
with an existing ID constructs the replacement first and swaps it atomically.

Scenario tools clone the source into a private candidate. The candidate is only
published after all modifications and any requested simulation succeed; failed
scenarios are unloaded automatically. Explicit scenario-ID collisions are
rejected, while omitted IDs receive a collision-resistant suffix.

Changes made through modification tools remain in the loaded in-memory session
and are included in later simulations. `unload_network` discards that session;
call `save_network` first when the modified model must persist on disk.

**Simulation model**: Editable sessions use persistent project handles, but each
simulation is run from a fresh input-file snapshot on a separate solver handle.
This prevents transient solver state from leaking into later operations. Because
ePyT currently creates intermediate files relative to the process working
directory, directory-changing solver calls are serialized and run in temporary
workspaces that are always restored and removed.

Scenario results include lineage and a machine-readable change manifest. Leak
emitters are calibrated from a requested target flow and reference pressure (or
from a baseline flow fraction), and contamination intervals use the model's
pattern timestep. Injection boundaries must align with that timestep; use
`set_pattern_timestep` when finer scheduling is required.

---

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Bundled networks

ePyT ships with many standard benchmark networks including Net1, Net2, L-TOWN,
Hanoi, Anytown, Balerma and others.  Use `list_bundled_networks` to discover
them all.

---

## License

MIT

<!-- mcp-name: io.github.Applied-Artificial-Intelligence-Eurecat/epanet-mcp-server -->
