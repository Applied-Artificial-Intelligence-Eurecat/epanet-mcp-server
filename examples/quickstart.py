"""
Quickstart: exercise the EPANET MCP Server tools directly (no MCP transport needed).

Run with:
    cd epanet-mcp-server
    PYTHONPATH=src python examples/quickstart.py
"""

from epanet_mcp.tools import inspection, simulation, modification, scenarios

# ── 1. Load bundled Net1 ─────────────────────────────────────────────────────
print("=== Loading Net1.inp ===")
result = inspection.load_network("Net1.inp", network_id="net1")
print(f"Loaded: {result['network_id']}  path: {result['path']}")
summary = result["summary"]
print(
    f"  Nodes: {summary['nodes']['total']}  "
    f"(junctions={summary['nodes']['junctions']}, "
    f"tanks={summary['nodes']['tanks']}, "
    f"reservoirs={summary['nodes']['reservoirs']})"
)
print(
    f"  Links: {summary['links']['total']}  "
    f"(pipes={summary['links']['pipes']}, pumps={summary['links']['pumps']})"
)

# ── 2. Inspect nodes and links ───────────────────────────────────────────────
print("\n=== Nodes ===")
nodes = inspection.get_nodes("net1")["nodes"]
for n in nodes[:4]:
    print(f"  {n['id']:8s}  type={n['type']:12s}  elev={n['elevation']:.1f}")

print("\n=== Links ===")
links = inspection.get_links("net1")["links"]
for lnk in links[:4]:
    print(
        f"  {lnk['id']:8s}  {lnk['type']:8s}  "
        f"{lnk['from_node']} → {lnk['to_node']}  "
        f"diam={lnk['diameter']}"
    )

# ── 3. Run hydraulic simulation ──────────────────────────────────────────────
print("\n=== Hydraulic Simulation ===")
sim = simulation.run_hydraulic_simulation("net1")
times = sim["time_steps_s"]
pressures = sim["pressure"]
node_ids = sim["node_ids"]
# pressures at t=3600s
p_at_1h = simulation.get_pressure_at_time("net1", 3600)
print(f"  Pressures at t=1h (node: pressure):")
for nid, p in sorted(p_at_1h["pressures"].items(), key=lambda x: x[0]):
    print(f"    {nid:8s}: {p:6.2f}")

# ── 4. Modify a pipe diameter and re-simulate ────────────────────────────────
print("\n=== Modifying pipe 10 diameter: 18 → 300 mm ===")
modification.set_pipe_diameter("net1", "10", 300.0)
sim2 = simulation.get_pressure_at_time("net1", 3600)
print("  Pressures after diameter change:")
for nid, p in sorted(sim2["pressures"].items(), key=lambda x: x[0]):
    old_p = p_at_1h["pressures"].get(nid, 0)
    delta = p - old_p
    print(f"    {nid:8s}: {p:6.2f}  (Δ {delta:+.2f})")

# ── 5. Demand perturbation scenario ─────────────────────────────────────────
print("\n=== Demand Perturbation Scenario (×2 at node 11) ===")
dem_result = scenarios.create_demand_perturbation(
    "net1",
    node_demands={"11": 2.0, "12": 2.0},
    scenario_id="high_demand",
    run_simulation=True,
)
p_high = {
    nid: dem_result["simulation"]["pressure"][-1][i]
    for i, nid in enumerate(dem_result["simulation"]["node_ids"])
}
print("  Pressures at end of high-demand simulation:")
for nid, p in sorted(p_high.items()):
    print(f"    {nid:8s}: {p:.2f}")

# ── 6. Leakage event ─────────────────────────────────────────────────────────
print("\n=== Leakage Event (pipe 10, 15% leakage) ===")
leak = scenarios.create_leakage_event(
    "net1",
    pipe_id="10",
    leak_fraction=0.15,
    scenario_id="leak_10",
    run_simulation=True,
)
print(f"  Leak node: {leak['leak_node']}")
print(f"  Pipe split into: {leak['pipe_split_into']}")
print(f"  Simulation steps: {len(leak['simulation']['time_steps_s'])}")

# ── 7. Contamination event ──────────────────────────────────────────────────
print("\n=== Contamination Event (node 11, 10 mg/L, hours 1-3) ===")
contam = scenarios.create_contamination_event(
    "net1",
    source_node_id="11",
    concentration=10.0,
    start_time_s=3600,
    end_time_s=10800,
    scenario_id="contam_11",
    run_simulation=True,
)
print(f"  Pattern id: {contam['pattern_id']}")
max_quality = max(max(row) for row in contam["simulation"]["node_quality"] if row)
print(f"  Max node quality reached: {max_quality:.4f} mg/L")

print("\n=== Done ===")
