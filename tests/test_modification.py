"""Tests for modification tools."""

import os
import tempfile

import pytest

from epanet_mcp.session import registry
from epanet_mcp.tools import modification, simulation, inspection


def test_set_pipe_diameter(net1):
    sess = registry.require(net1)
    idx = sess.d.getLinkIndex("10")
    old_d = sess.d.getLinkDiameter(idx)
    result = modification.set_pipe_diameter(net1, "10", 200.0)
    assert result["diameter"] == 200.0
    new_d = sess.d.getLinkDiameter(idx)
    assert abs(new_d - 200.0) < 0.01


def test_set_pipe_roughness(net1):
    result = modification.set_pipe_roughness(net1, "10", 110.0)
    assert result["roughness"] == 110.0


def test_set_pipe_status_closed(net1):
    result = modification.set_pipe_status(net1, "10", "CLOSED")
    assert result["status"] == "CLOSED"


def test_set_pipe_status_open(net1):
    result = modification.set_pipe_status(net1, "10", "OPEN")
    assert result["status"] == "OPEN"


def test_set_pipe_length(net1):
    result = modification.set_pipe_length(net1, "10", 500.0)
    assert result["length"] == 500.0


def test_set_node_base_demand(net1):
    result = modification.set_node_base_demand(net1, "11", 200.0)
    assert result["base_demand"] == 200.0


def test_set_pump_status(net1):
    # Net1 has pump named "9"
    result = modification.set_pump_status(net1, "9", "CLOSED")
    assert result["status"] == "CLOSED"


def test_set_pump_speed(net1):
    result = modification.set_pump_speed(net1, "9", 0.8)
    assert result["speed"] == 0.8


def test_set_tank_parameters(net1):
    # Tank "2" in Net1
    result = modification.set_tank_parameters(net1, "2", initial_level=15.0, max_level=30.0)
    assert result["initial_level"] == 15.0
    assert result["max_level"] == 30.0


def test_set_reservoir_head(net1):
    # Reservoir "9" in Net1
    result = modification.set_reservoir_head(net1, "9", 200.0)
    assert result["head"] == 200.0


def test_set_simulation_duration(net1):
    result = modification.set_simulation_duration(net1, 43200)
    assert result["simulation_duration_s"] == 43200
    opts = inspection.get_options(net1)
    assert opts["simulation_duration_s"] == 43200


def test_set_hydraulic_timestep(net1):
    result = modification.set_hydraulic_timestep(net1, 1800)
    assert result["hydraulic_timestep_s"] == 1800


def test_set_quality_timestep(net1):
    result = modification.set_quality_timestep(net1, 300)
    assert result["quality_timestep_s"] == 300


def test_set_quality_type_age(net1):
    result = modification.set_quality_type(net1, "AGE")
    assert result["quality_type"] == "AGE"


def test_add_and_get_pattern(net1):
    result = modification.add_pattern(net1, "TestPat", [1.0, 1.2, 0.8, 1.0])
    assert result["pattern_id"] == "TestPat"
    patterns = inspection.get_patterns(net1)
    pat_ids = [p["id"] for p in patterns["patterns"]]
    assert "TestPat" in pat_ids


def test_add_control(net1):
    result = modification.add_control(net1, "LINK 9 CLOSED IF NODE 2 ABOVE 200")
    assert "control_index" in result
    assert result["control_index"] >= 1


def test_save_network(net1):
    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, "net1_modified.inp")
        result = modification.save_network(net1, out_path)
        assert result["saved"] is True
        assert os.path.exists(out_path)
        # verify it can be loaded back
        r2 = inspection.load_network(out_path, network_id="net1_saved")
        assert r2["network_id"] == "net1_saved"
