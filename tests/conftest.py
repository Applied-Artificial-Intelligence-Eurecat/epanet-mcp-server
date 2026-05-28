"""Shared pytest fixtures."""

import pytest
from epanet_mcp.session import registry
from epanet_mcp.tools import inspection

NET1_NAME = "Net1.inp"
NET1_ID = "net1_test"


@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure registry is clean before and after each test."""
    registry.clear()
    yield
    registry.clear()


@pytest.fixture()
def net1():
    """Load the bundled Net1.inp and return its network_id."""
    result = inspection.load_network(NET1_NAME, network_id=NET1_ID)
    assert result["network_id"] == NET1_ID
    return NET1_ID
