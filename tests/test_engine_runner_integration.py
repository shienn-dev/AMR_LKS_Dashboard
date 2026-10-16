"""Integration tests: SimulationEngine + MissionRunner (Phase 2).

Unit tests; injected clock via ``engine.tick(dt)``, no threads, no ROS 2.
"""

from __future__ import annotations

from amr_core.mission import MissionConfig
from amr_core.mission_runner import MissionRunner, RunnerState, mission_status
from amr_core.mock_platform import ScriptedSkill
from amr_core.simulation import SimulationEngine
from amr_core.states import RobotState


def _engine_with_runner(go_to: list[str], return_home: list[str], go_dur: float = 5.0,
                        home_dur: float = 5.0) -> SimulationEngine:
    engine = SimulationEngine()
    engine.mission = MissionConfig(
        mission_id="modul_E",
        version=1,
        time_limit_s=600,
        reserve_for_home_s=60,
        target_order=["T1", "T2"],
        rack_colors={"rack_A": "red", "rack_B": "green", "rack_C": "blue"},
    )
    skills = {
        "go_to": ScriptedSkill("go_to", script=go_to, duration_s=go_dur),
        "return_home": ScriptedSkill("return_home", script=return_home, duration_s=home_dur),
    }
    runner = MissionRunner(spec=_spec_of(engine), skills=skills, log=engine.log)
    engine.attach_runner(runner)
    return engine


def _spec_of(engine: SimulationEngine):
    # Build a spec from the engine's mission via the adapter, for the runner.
    from amr_core.mission import spec_from_config

    assert engine.mission is not None
    return spec_from_config(engine.mission, default_timeout_s=10.0)


def _drive(engine: SimulationEngine, dt: float = 1.0, limit: int = 2000) -> None:
    for _ in range(limit):
        engine.tick(dt)
        if engine.state is not RobotState.RUNNING:
            break


def test_runner_mission_reaches_done() -> None:
    engine = _engine_with_runner(["SUCCESS", "SUCCESS"], ["SUCCESS"])
    engine.start_mission()
    assert engine.state is RobotState.RUNNING
    _drive(engine)
    assert engine.state is RobotState.DONE


def test_engine_owns_state_runner_does_not_touch_it() -> None:
    engine = _engine_with_runner(["SUCCESS", "SUCCESS"], ["SUCCESS"])
    engine.start_mission()
    engine.tick(1.0)
    # The engine's state is owned by the engine, not by the runner.
    assert engine.state in (RobotState.RUNNING, RobotState.DONE)
    assert engine.runner is not None
    # The runner has no reference to engine.state.
    assert not hasattr(engine.runner, "state_transition")


def test_mission_failure_maps_to_failed_state() -> None:
    engine = _engine_with_runner(["FAILURE", "FAILURE"], ["SUCCESS"])
    engine.start_mission()
    _drive(engine)
    assert engine.state is RobotState.FAILED


def test_health_failure_during_run_cancels_skill_and_fails() -> None:
    engine = _engine_with_runner(["SUCCESS"], ["SUCCESS"], go_dur=999.0)
    engine.start_mission()
    engine.tick(1.0)  # start first go_to (long)
    engine.apply_health("lidar", False)  # critical failure
    assert engine.state is RobotState.FAILED


def test_reset_cancels_skill_before_ready() -> None:
    engine = _engine_with_runner(["SUCCESS"], ["SUCCESS"], go_dur=999.0)
    engine.start_mission()
    engine.tick(1.0)  # start first step
    engine.fail_mission("simulated")
    assert engine.state is RobotState.FAILED
    engine.reset()
    assert engine.state is RobotState.READY
    # The return_home/go_to skill must not be left running.
    go_to = engine.runner.skills["go_to"]  # type: ignore[attr-defined]
    assert go_to.cancelled


def test_legacy_path_still_works_without_runner() -> None:
    # No runner attached -> legacy synthetic cadence (Phase 1 behavior).
    engine = SimulationEngine()
    engine.mission = MissionConfig(
        mission_id="modul_E",
        version=1,
        time_limit_s=600,
        reserve_for_home_s=60,
        target_order=["T1", "T2"],
        rack_colors={"rack_A": "red", "rack_B": "green", "rack_C": "blue"},
    )
    assert engine.runner is None
    engine.start_mission()
    for _ in range(500):
        engine.tick(2.0)
        if engine.state is not RobotState.RUNNING:
            break
    assert engine.state is RobotState.DONE


def test_mission_status_view_model() -> None:
    engine = _engine_with_runner(["SUCCESS", "SUCCESS"], ["SUCCESS"])
    engine.start_mission()
    engine.tick(1.0)
    status = mission_status(engine.runner)  # type: ignore[arg-type]
    assert status is not None
    assert status.total_steps == 3
    assert 0 <= status.progress_fraction <= 1.0


def test_mission_status_none_without_runner() -> None:
    assert mission_status(None) is None


# --------------------------------------------------------------------------- #
# Regression (audit finding 5.1): apply_health() must abort the active skill
# during RUNNING, exactly like the tick() path (OPS-11).
# --------------------------------------------------------------------------- #

def test_apply_health_aborts_active_skill_and_finishes_runner() -> None:
    """A critical failure reported via ``apply_health`` (the UI health switch
    path) must cancel the active skill through ``runner.abort`` and leave the
    runner FINISHED — not just move the engine to FAILED."""
    engine = _engine_with_runner(["SUCCESS"], ["SUCCESS"], go_dur=999.0)
    engine.start_mission()
    engine.tick(1.0)  # starts the first go_to and leaves it active

    runner = engine.runner
    assert runner is not None
    go_to = runner.skills["go_to"]  # type: ignore[attr-defined]
    assert not go_to.cancelled  # still running before the failure

    engine.apply_health("lidar", False)  # critical failure during RUNNING

    assert engine.state is RobotState.FAILED
    # The runner must no longer be RUNNING; per the current contract it ends
    # FINISHED after an external abort.
    assert runner.state is RunnerState.FINISHED  # type: ignore[attr-defined]
    # The active skill must have received cancel() (via runner.abort), not just
    # a state change on the engine.
    assert go_to.cancelled is True
    # Reason is consistent with the tick() path.
    assert runner.terminal_reason == "aborted:health:LiDAR"  # type: ignore[attr-defined]


def test_apply_health_non_critical_keeps_runner_running() -> None:
    """A non-critical health change must not stop the mission nor cancel any
    skill (preserves pre-existing behaviour)."""
    engine = _engine_with_runner(["SUCCESS"], ["SUCCESS"], go_dur=999.0)
    engine.start_mission()
    engine.tick(1.0)

    runner = engine.runner
    assert runner is not None
    engine.apply_health("battery", False)  # battery is not critical

    assert engine.state is RobotState.RUNNING
    assert runner.state is RunnerState.RUNNING  # type: ignore[attr-defined]
    assert runner.skills["go_to"].cancelled is False  # type: ignore[attr-defined]


def test_apply_health_critical_without_runner_unaffected() -> None:
    """Without a runner the pre-run behaviour is unchanged: READY -> FAULT."""
    engine = SimulationEngine()
    assert engine.runner is None
    engine.apply_health("lidar", False)
    assert engine.state is RobotState.FAULT
    assert "LiDAR" in engine.last_reason


def test_apply_health_critical_repeated_does_not_double_abort() -> None:
    """A second critical failure must not re-abort an already FINISHED runner
    (the RUNNING guard makes the abort path idempotent)."""
    engine = _engine_with_runner(["SUCCESS"], ["SUCCESS"], go_dur=999.0)
    engine.start_mission()
    engine.tick(1.0)
    engine.apply_health("lidar", False)
    runner = engine.runner
    assert runner is not None
    assert runner.state is RunnerState.FINISHED  # type: ignore[attr-defined]
    reason_after_first = runner.terminal_reason  # type: ignore[attr-defined]

    # A second, different critical component fails while already FAILED.
    engine.apply_health("camera", False)

    assert engine.state is RobotState.FAILED
    assert runner.terminal_reason == reason_after_first  # type: ignore[attr-defined]
