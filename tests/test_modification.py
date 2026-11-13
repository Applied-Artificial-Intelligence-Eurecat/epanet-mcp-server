"""Tests for modification tools."""

import os
import tempfile

import pytest

from epanet_mcp.session import registry
from epanet_mcp.tools import inspection, modification


def test_set_pipe_diameter(net1):
    sess = registry.require(net1)
    idx = sess.d.getLinkIndex("10")
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
    assert result["demand_category"] == 1


def test_set_node_base_demand_honors_category(net1):
    with registry.lease(net1) as session:
        node_index = session.d.getNodeIndex("11")
        session.d.addNodeJunctionDemand(node_index, 25.0, "", "secondary")

    result = modification.set_node_base_demand(net1, "11", 40.0, demand_category=2)

    with registry.lease(net1) as session:
        demands = session.d.getNodeBaseDemands(node_index)
    assert result["demand_category"] == 2
    assert demands[1][0] != 40.0
    assert demands[2][0] == pytest.approx(40.0)


def test_set_node_base_demand_rejects_missing_category(net1):
    with pytest.raises(ValueError, match="does not exist"):
        modification.set_node_base_demand(net1, "11", 40.0, demand_category=2)


def test_set_pump_status(net1):
    # Net1 has pump named "9"
    result = modification.set_pump_status(net1, "9", "CLOSED")
    assert result["status"] == "CLOSED"


@pytest.mark.parametrize(
    ("function", "asset_id"),
    [
        (modification.set_pipe_status, "10"),
        (modification.set_pump_status, "9"),
    ],
)
def test_link_status_rejects_invalid_values(net1, function, asset_id):
    with pytest.raises(ValueError, match="status must be one of"):
        function(net1, asset_id, "STOP")


def test_pipe_status_rejects_non_pipe_asset(net1):
    with pytest.raises(ValueError, match="Unknown pipe"):
        modification.set_pipe_status(net1, "9", "CLOSED")


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
def test_pipe_diameter_requires_positive_finite_value(net1, value):
    with pytest.raises(ValueError, match="diameter"):
        modification.set_pipe_diameter(net1, "10", value)


def test_set_pump_speed(net1):
    result = modification.set_pump_speed(net1, "9", 0.8)
    assert result["speed"] == 0.8


def test_set_tank_parameters(net1):
    # Tank "2" in Net1
    result = modification.set_tank_parameters(
        net1, "2", initial_level=125.0, max_level=160.0
    )
    assert result["initial_level"] == 125.0
    assert result["max_level"] == 160.0


def test_set_tank_parameters_validates_effective_range(net1):
    with pytest.raises(ValueError, match="initial_level must be less"):
        modification.set_tank_parameters(net1, "2", max_level=110.0)


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


def test_set_pattern_timestep(net1):
    result = modification.set_pattern_timestep(net1, 1800)
    assert result["pattern_timestep_s"] == 1800
    assert inspection.get_options(net1)["pattern_timestep_s"] == 1800


def test_timestep_rejects_zero(net1):
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        modification.set_hydraulic_timestep(net1, 0)


def test_set_quality_type_age(net1):
    result = modification.set_quality_type(net1, "AGE")
    assert result["quality_type"] == "AGE"


def test_trace_quality_requires_node(net1):
    with pytest.raises(ValueError, match="tracer_node is required"):
        modification.set_quality_type(net1, "TRACE")


def test_pump_curve_rejects_mismatched_arrays(net1):
    with pytest.raises(ValueError, match="same length"):
        modification.set_pump_head_curve(net1, "9", [0.0, 10.0], [100.0])


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
