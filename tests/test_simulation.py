"""Tests for simulation tools."""

from concurrent.futures import ThreadPoolExecutor

from epanet_mcp.tools import inspection
from epanet_mcp.tools import simulation


def test_run_hydraulic_simulation(net1):
    result = simulation.run_hydraulic_simulation(net1)
    assert result["network_id"] == net1
    assert len(result["time_steps_s"]) > 1
    assert len(result["node_ids"]) == 11
    assert len(result["link_ids"]) == 13
    # pressure is a list of lists (timestep × node)
    assert len(result["pressure"]) > 0
    assert any(value > 0 for row in result["pressure"] for value in row)
    assert any(value != 0 for row in result["flow"] for value in row)


def test_run_quality_simulation(net1):
    result = simulation.run_quality_simulation(net1)
    assert result["network_id"] == net1
    assert "node_quality" in result
    assert "link_quality" in result
    assert len(result["time_steps_s"]) > 0


def test_run_full_simulation(net1):
    result = simulation.run_full_simulation(net1)
    assert "pressure" in result
    assert "node_quality" in result
    assert "flow" in result
    assert "reaction_rate" in result


def test_get_pressure_at_time(net1):
    result = simulation.get_pressure_at_time(net1, time_s=3600)
    assert "pressures" in result
    assert len(result["pressures"]) == 11
    # pressures should be positive for Net1
    for v in result["pressures"].values():
        assert isinstance(v, (int, float))


def test_get_flow_at_time(net1):
    result = simulation.get_flow_at_time(net1, time_s=3600)
    assert "flows" in result
    assert len(result["flows"]) == 13


def test_get_pressure_at_time_0(net1):
    result = simulation.get_pressure_at_time(net1, time_s=0)
    assert result["actual_time_s"] >= 0


def test_parallel_sessions_run_without_workspace_interference(net1):
    other_id = "net1_parallel"
    inspection.load_network("Net1.inp", network_id=other_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(simulation.run_hydraulic_simulation, net1)
        second = executor.submit(simulation.run_hydraulic_simulation, other_id)
        first_result = first.result(timeout=10)
        second_result = second.result(timeout=10)

    assert first_result["network_id"] == net1
    assert second_result["network_id"] == other_id
    assert first_result["time_steps_s"] == second_result["time_steps_s"]
    assert first_result["pressure"] == second_result["pressure"]
