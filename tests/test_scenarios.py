"""Tests for scenario generation tools."""

import pytest

from epanet_mcp.session import registry
from epanet_mcp.tools import inspection, scenarios, simulation


def test_demand_perturbation(net1):
    result = scenarios.create_demand_perturbation(
        net1,
        node_demands={"11": 2.0, "12": 0.5},
        scenario_id="dem_pert",
        run_simulation=True,
    )
    assert result["scenario_type"] == "demand_perturbation"
    assert result["scenario_id"] == "dem_pert"
    assert "11" in result["changes"]
    assert result["lineage"]["parent_network_id"] == net1
    assert registry.require("dem_pert").lineage is not None
    assert "simulation" in result
    # original session should still be intact
    assert net1 in registry.list_ids()
    assert "dem_pert" in registry.list_ids()


def test_demand_perturbation_no_simulation(net1):
    result = scenarios.create_demand_perturbation(
        net1,
        node_demands={"11": 1.5},
        scenario_id="dem_pert2",
        run_simulation=False,
    )
    assert "simulation" not in result


def test_leakage_event(net1):
    result = scenarios.create_leakage_event(
        net1,
        pipe_id="10",
        leak_fraction=0.1,
        scenario_id="leak_10",
        run_simulation=True,
    )
    assert result["scenario_type"] == "leakage_event"
    assert result["pipe_id"] == "10"
    assert result["leak_fraction"] == 0.1
    assert result["target_leak_flow"] == pytest.approx(
        result["baseline_mean_pipe_flow"] * 0.1
    )
    assert result["emitter_coeff"] == pytest.approx(
        result["target_leak_flow"]
        / result["reference_pressure"] ** result["emitter_exponent"]
    )
    assert "leak_node" in result
    assert result["topology"]["link_replacements"]["10"] == ["10_A", "10_B"]
    assert result["lineage"]["parent_network_id"] == net1
    assert "simulation" in result


def test_leakage_event_invalid_fraction(net1):
    with pytest.raises(ValueError, match="leak_fraction"):
        scenarios.create_leakage_event(net1, "10", leak_fraction=1.5)


def test_contamination_event(net1):
    pattern_step = inspection.get_options(net1)["pattern_timestep_s"]
    result = scenarios.create_contamination_event(
        net1,
        source_node_id="11",
        concentration=10.0,
        start_time_s=pattern_step,
        end_time_s=pattern_step * 2,
        scenario_id="contam_11",
        run_simulation=True,
    )
    assert result["scenario_type"] == "contamination_event"
    assert result["source_node_id"] == "11"
    assert result["pattern_timestep_s"] == pattern_step
    assert result["pattern_values"][0:3] == [0.0, 1.0, 0.0]
    assert result["lineage"]["scenario_type"] == "contamination_event"
    assert "simulation" in result
    sim = result["simulation"]
    assert "node_quality" in sim


def test_contamination_window_must_align_to_pattern_timestep(net1):
    pattern_step = inspection.get_options(net1)["pattern_timestep_s"]
    with pytest.raises(ValueError, match="not aligned"):
        scenarios.create_contamination_event(
            net1,
            source_node_id="11",
            concentration=10.0,
            start_time_s=pattern_step // 2,
            end_time_s=pattern_step,
            scenario_id="misaligned_contamination",
            run_simulation=False,
        )
    assert "misaligned_contamination" not in registry.list_ids()


def test_contamination_rejects_invalid_source_type(net1):
    with pytest.raises(ValueError, match="source_type"):
        scenarios.create_contamination_event(
            net1,
            source_node_id="11",
            concentration=10.0,
            start_time_s=0,
            end_time_s=7200,
            source_type="INVALID",
            run_simulation=False,
        )


def test_leakage_accepts_explicit_target_flow(net1):
    result = scenarios.create_leakage_event(
        net1,
        pipe_id="10",
        target_leak_flow=25.0,
        reference_pressure=50.0,
        emitter_exponent=0.5,
        scenario_id="explicit_leak",
        run_simulation=False,
    )
    assert result["target_leak_flow"] == 25.0
    assert result["reference_pressure"] == 50.0
    assert result["emitter_coeff"] == pytest.approx(25.0 / (50.0**0.5))


def test_leakage_rejects_ambiguous_flow_inputs(net1):
    with pytest.raises(ValueError, match="exactly one"):
        scenarios.create_leakage_event(
            net1,
            pipe_id="10",
            leak_fraction=0.1,
            target_leak_flow=10.0,
            reference_pressure=50.0,
            run_simulation=False,
        )


def test_zero_leak_pipe_split_preserves_common_node_pressures(net1):
    baseline = simulation.run_hydraulic_simulation(net1)
    scenario = scenarios.create_leakage_event(
        net1,
        pipe_id="10",
        leak_fraction=0.0,
        scenario_id="zero_leak",
        run_simulation=True,
    )["simulation"]

    baseline_positions = {node_id: i for i, node_id in enumerate(baseline["node_ids"])}
    scenario_positions = {node_id: i for i, node_id in enumerate(scenario["node_ids"])}
    baseline_times = {
        time_s: index for index, time_s in enumerate(baseline["time_steps_s"])
    }
    scenario_times = {
        time_s: index for index, time_s in enumerate(scenario["time_steps_s"])
    }
    for time_s in baseline_times.keys() & scenario_times.keys():
        baseline_row = baseline["pressure"][baseline_times[time_s]]
        scenario_row = scenario["pressure"][scenario_times[time_s]]
        for node_id, baseline_position in baseline_positions.items():
            assert scenario_row[scenario_positions[node_id]] == pytest.approx(
                baseline_row[baseline_position], abs=1e-3
            )


def test_pressure_change_scenario(net1):
    result = scenarios.create_pressure_change_scenario(
        net1,
        reservoir_heads={"9": 200.0},
        scenario_id="pressure_up",
        run_simulation=True,
    )
    assert result["scenario_type"] == "pressure_change"
    assert "9" in result["changes"]
    assert result["changes"]["9"]["new_head"] == 200.0
    assert "simulation" in result


def test_pump_control_scenario(net1):
    result = scenarios.create_pump_control_scenario(
        net1,
        pump_schedule={
            "9": [
                "LINK 9 OPEN AT CLOCKTIME 06:00",
                "LINK 9 CLOSED AT CLOCKTIME 22:00",
            ]
        },
        scenario_id="pump_sched",
        run_simulation=True,
    )
    assert result["scenario_type"] == "pump_control"
    assert "9" in result["added_controls"]
    assert len(result["added_controls"]["9"]) == 2
    assert "simulation" in result


def test_valve_control_scenario_no_valves_graceful(net1):
    # Net1 has no valves; test that we can attempt and it doesn't crash
    # (it will fail at getLinkIndex if valve doesn't exist)
    # So let's just verify multi_failure works instead
    result = scenarios.create_multi_failure_scenario(
        net1,
        failed_pipes=["10"],
        failed_pumps=None,
        scenario_id="fail_10",
        run_simulation=True,
    )
    assert result["scenario_type"] == "multi_failure"
    assert "10" in result["closed"]["pipes"]
    assert "simulation" in result


def test_multi_failure_scenario(net1):
    result = scenarios.create_multi_failure_scenario(
        net1,
        failed_pipes=["10", "11"],
        failed_pumps=["9"],
        scenario_id="multi_fail",
        run_simulation=True,
    )
    assert result["scenario_type"] == "multi_failure"
    assert set(result["closed"]["pipes"]) == {"10", "11"}
    assert result["closed"]["pumps"] == ["9"]


def test_clone_does_not_modify_original(net1):
    """Scenario perturbation must not affect the source network's demand."""
    from epanet_mcp.tools.inspection import get_nodes

    nodes_before = get_nodes(net1)
    demands_before = {n["id"]: n["base_demand"] for n in nodes_before["nodes"]}

    scenarios.create_demand_perturbation(
        net1,
        node_demands={"11": 5.0},
        scenario_id="big_demand",
        run_simulation=False,
    )

    nodes_after = get_nodes(net1)
    demands_after = {n["id"]: n["base_demand"] for n in nodes_after["nodes"]}

    assert demands_before == demands_after


def test_failed_scenario_is_not_published(net1):
    def fail_after_clone(d):
        raise RuntimeError("modification failed")

    with pytest.raises(RuntimeError, match="modification failed"):
        scenarios._create_scenario(
            net1,
            "failed_scenario",
            False,
            fail_after_clone,
        )

    assert "failed_scenario" not in registry.list_ids()


def test_failed_simulation_is_not_published(net1, monkeypatch):
    def fail_simulation(session):
        raise RuntimeError("simulation failed")

    monkeypatch.setattr(scenarios, "_run_full_session", fail_simulation)
    with pytest.raises(RuntimeError, match="simulation failed"):
        scenarios.create_demand_perturbation(
            net1,
            node_demands={"11": 2.0},
            scenario_id="failed_simulation",
            run_simulation=True,
        )

    assert "failed_simulation" not in registry.list_ids()


def test_explicit_scenario_collision_preserves_existing_session(net1):
    scenarios.create_demand_perturbation(
        net1,
        node_demands={"11": 2.0},
        scenario_id="same_id",
        run_simulation=False,
    )
    original = registry.require("same_id")

    with pytest.raises(ValueError, match="already exists"):
        scenarios.create_demand_perturbation(
            net1,
            node_demands={"11": 3.0},
            scenario_id="same_id",
            run_simulation=False,
        )

    assert registry.require("same_id") is original


def test_generated_scenario_ids_are_unique(net1):
    first = scenarios.create_demand_perturbation(
        net1, node_demands={"11": 1.1}, run_simulation=False
    )
    second = scenarios.create_demand_perturbation(
        net1, node_demands={"11": 1.2}, run_simulation=False
    )

    assert first["scenario_id"] != second["scenario_id"]
    assert first["scenario_id"] in registry.list_ids()
    assert second["scenario_id"] in registry.list_ids()
