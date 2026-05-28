"""Tests for simulation tools."""

import pytest
from epanet_mcp.tools import simulation


def test_run_hydraulic_simulation(net1):
    result = simulation.run_hydraulic_simulation(net1)
    assert result["network_id"] == net1
    assert len(result["time_steps_s"]) > 0
    assert len(result["node_ids"]) == 11
    assert len(result["link_ids"]) == 13
    # pressure is a list of lists (timestep × node)
    assert len(result["pressure"]) > 0


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
