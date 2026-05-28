"""Tests for inspection tools."""

import pytest
from epanet_mcp.tools import inspection
from epanet_mcp.session import registry


def test_list_bundled_networks():
    result = inspection.list_bundled_networks()
    assert "bundled_networks" in result
    names = result["bundled_networks"]
    assert any("Net1" in n for n in names)


def test_load_network_by_name(net1):
    assert net1 == "net1_test"
    ids = registry.list_ids()
    assert "net1_test" in ids


def test_load_network_bad_path():
    with pytest.raises(FileNotFoundError):
        inspection.load_network("/nonexistent/path/bad.inp")


def test_unload_network(net1):
    result = inspection.unload_network(net1)
    assert result["unloaded"] is True
    assert net1 not in registry.list_ids()


def test_list_networks(net1):
    result = inspection.list_networks()
    assert net1 in result["loaded_networks"]


def test_network_summary(net1):
    s = inspection.get_network_summary(net1)
    assert s["nodes"]["total"] == 11
    assert s["links"]["total"] == 13
    assert s["nodes"]["junctions"] == 9
    assert s["nodes"]["tanks"] == 1
    assert s["nodes"]["reservoirs"] == 1
    assert s["links"]["pipes"] == 12
    assert s["links"]["pumps"] == 1


def test_get_nodes(net1):
    result = inspection.get_nodes(net1)
    nodes = result["nodes"]
    assert len(nodes) == 11
    ids = [n["id"] for n in nodes]
    assert "10" in ids or "11" in ids  # Net1 junction names


def test_get_links(net1):
    result = inspection.get_links(net1)
    links = result["links"]
    assert len(links) == 13
    for lnk in links:
        assert "from_node" in lnk
        assert "to_node" in lnk


def test_get_patterns(net1):
    result = inspection.get_patterns(net1)
    assert "patterns" in result
    assert len(result["patterns"]) >= 1


def test_get_controls(net1):
    result = inspection.get_controls(net1)
    assert "controls" in result


def test_get_curves(net1):
    result = inspection.get_curves(net1)
    assert "curves" in result
    assert len(result["curves"]) >= 1


def test_get_options(net1):
    result = inspection.get_options(net1)
    assert "flow_units" in result
    assert "simulation_duration_s" in result
    assert result["simulation_duration_s"] > 0


def test_require_unknown_raises():
    with pytest.raises(ValueError, match="No network loaded"):
        registry.require("nonexistent")
