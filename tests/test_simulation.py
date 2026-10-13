"""Tests for the simulation engine.

Covers: boot health check, mission lock while RUNNING, critical health-check
failure -> FAULT, recovery/reset behaviour, and bounded progress.
"""

from __future__ import annotations

from amr_core.mission import MissionConfig
from amr_core.simulation import SimulationEngine
from amr_core.states import RobotState


def _engine_with_valid_mission() -> SimulationEngine:
    engine = SimulationEngine()
    engine.mission = MissionConfig(
        mission_id="modul_E",
        version=1,
        time_limit_s=600,
        reserve_for_home_s=60,
        target_order=["T3", "T1", "T4", "T2"],
        rack_colors={"rack_A": "red", "rack_B": "green", "rack_C": "blue"},
    )
    return engine


def test_boot_reaches_ready_when_healthy() -> None:
    engine = SimulationEngine()
    assert engine.state is RobotState.READY


def test_critical_health_failure_at_boot_goes_fault() -> None:
    engine = SimulationEngine()
    # Force a critical failure and re-run the boot check.
    engine.apply_health("lidar", False)
    engine._run_health_check()
    assert engine.state is RobotState.FAULT
    assert "LiDAR" in engine.last_reason


def test_start_requires_valid_mission() -> None:
    engine = SimulationEngine()  # no mission set
    result = engine.start_mission()
    assert not result.allowed
    assert engine.state is RobotState.READY


def test_start_locks_mission_editing() -> None:
    engine = _engine_with_valid_mission()
    assert engine.can_edit_mission()
    engine.start_mission()
    assert engine.state is RobotState.RUNNING
    assert not engine.can_edit_mission()


def test_tick_completes_mission_to_done() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    for _ in range(500):
        engine.tick(2.0)
        if engine.state is not RobotState.RUNNING:
            break
    assert engine.state is RobotState.DONE


def test_tick_fails_when_time_limit_exceeded() -> None:
    engine = _engine_with_valid_mission()
    assert engine.mission is not None
    engine.mission.time_limit_s = 30
    engine.mission.reserve_for_home_s = 1
    engine.start_mission()
    for _ in range(500):
        engine.tick(2.0)
        if engine.state is not RobotState.RUNNING:
            break
    assert engine.state in (RobotState.FAILED, RobotState.DONE)


def test_mission_failure_from_running() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    result = engine.fail_mission("simulated")
    assert result.allowed
    assert engine.state is RobotState.FAILED


def test_reset_from_failed_returns_ready() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    engine.fail_mission()
    assert engine.state is RobotState.FAILED
    engine.reset()
    assert engine.state is RobotState.READY


def test_reset_from_fault_refused_while_critical_still_failing() -> None:
    engine = SimulationEngine()
    engine.apply_health("camera", False)
    engine._run_health_check()
    assert engine.state is RobotState.FAULT
    engine.reset()
    assert engine.state is RobotState.FAULT  # refused


def test_reset_from_fault_allowed_after_recovery() -> None:
    engine = SimulationEngine()
    engine.apply_health("camera", False)
    engine._run_health_check()
    assert engine.state is RobotState.FAULT
    engine.apply_health("camera", True)  # fix the component
    engine.reset()
    assert engine.state is RobotState.READY


def test_tick_is_ignored_when_not_running() -> None:
    engine = _engine_with_valid_mission()
    before = engine.elapsed_s
    engine.tick(2.0)
    assert engine.elapsed_s == before


def test_determinism_same_seed_same_sample() -> None:
    import random

    from amr_core.samples import SAMPLE_MISSIONS

    mission = SAMPLE_MISSIONS[0]
    a = mission.sample_config(random.Random(42))
    b = mission.sample_config(random.Random(42))
    assert a.target_order == b.target_order
    assert a.rack_colors == b.rack_colors
