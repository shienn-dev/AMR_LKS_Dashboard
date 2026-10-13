"""Regression tests for the Phase 1.1 stabilization pass (F1–F5).

These cover the audit findings:

- F1  critical health failure during RUNNING stops mission progression
- F3  RESET cannot reach READY while a critical component is unhealthy
- F5  health changes go through the public engine API (no direct state writes)
- F2  event timestamps are stable and rendering is append-only
- F4  START is rejected with a clear reason in disallowed states
"""

from __future__ import annotations

from amr_core.mission import MissionConfig
from amr_core.simulation import SimulationEngine
from amr_core.states import Action, RobotState, transition


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


# --------------------------------------------------------------------------- #
# F1 — critical health failure during RUNNING
# --------------------------------------------------------------------------- #

def test_running_health_failure_transition_is_defined() -> None:
    result = transition(RobotState.RUNNING, Action.HEALTH_FAILED)
    assert result.allowed
    assert result.new_state is RobotState.FAILED


def test_critical_health_failure_during_running_fails_mission() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    assert engine.state is RobotState.RUNNING

    outcome = engine.apply_health("lidar", False)

    assert engine.state is RobotState.FAILED
    assert outcome.changed_state
    assert "LiDAR" in engine.last_reason


def test_running_health_failure_halts_progress_on_next_tick() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    # Fail a critical component directly on the health map (simulating a drop
    # that the tick path must notice) without going through apply_health.
    engine.health["lidar"].ok = False
    step_before = engine.step_index

    engine.tick(2.0)  # the normal update path must stop the run

    assert engine.state is RobotState.FAILED
    assert engine.step_index == step_before  # no further step progressed


def test_non_critical_failure_during_running_does_not_stop_mission() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    engine.apply_health("battery", False)  # battery is not critical
    assert engine.state is RobotState.RUNNING


# --------------------------------------------------------------------------- #
# F3 — RESET guarded by critical health on every applicable source state
# --------------------------------------------------------------------------- #

def test_reset_from_done_refused_while_critical_failing() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    engine.complete_mission()
    assert engine.state is RobotState.DONE
    engine.health["lidar"].ok = False

    result = engine.reset()

    assert not result.allowed
    assert engine.state is RobotState.DONE
    assert "RESET refused" in result.reason


def test_reset_from_failed_refused_while_critical_failing() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    engine.fail_mission("simulated")
    assert engine.state is RobotState.FAILED
    engine.health["camera"].ok = False

    result = engine.reset()

    assert not result.allowed
    assert engine.state is RobotState.FAILED
    assert "RESET refused" in result.reason


def test_reset_from_stopped_refused_while_critical_failing() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    engine._apply(Action.ESTOP_PRESSED)
    assert engine.state is RobotState.STOPPED
    engine.health["motor_controller"].ok = False

    result = engine.reset()

    assert not result.allowed
    assert engine.state is RobotState.STOPPED
    assert "RESET refused" in result.reason


def test_reset_from_fault_refused_while_critical_failing() -> None:
    engine = SimulationEngine()
    engine.apply_health("lidar", False)
    engine._run_health_check()
    assert engine.state is RobotState.FAULT

    result = engine.reset()

    assert not result.allowed
    assert engine.state is RobotState.FAULT


def test_reset_allowed_once_all_critical_recovered() -> None:
    engine = _engine_with_valid_mission()
    engine.start_mission()
    engine.fail_mission("simulated")
    engine.health["lidar"].ok = False
    assert not engine.reset().allowed

    engine.health["lidar"].ok = True  # recover
    result = engine.reset()

    assert result.allowed
    assert engine.state is RobotState.READY


# --------------------------------------------------------------------------- #
# F5 — public health API owns transitions
# --------------------------------------------------------------------------- #

def test_apply_health_returns_stable_result_without_state_write_from_caller() -> None:
    engine = SimulationEngine()
    assert engine.state is RobotState.READY
    outcome = engine.apply_health("camera", False)
    # The engine, not the caller, moved the state.
    assert engine.state is RobotState.FAULT
    assert outcome.transition.new_state is RobotState.FAULT


def test_apply_health_unknown_component_raises() -> None:
    engine = SimulationEngine()
    try:
        engine.apply_health("nope", False)
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected KeyError for unknown component")


def test_apply_health_noop_when_status_unchanged() -> None:
    engine = SimulationEngine()
    outcome = engine.apply_health("lidar", True)  # already OK
    assert not outcome.changed_state
    assert engine.state is RobotState.READY


# --------------------------------------------------------------------------- #
# F2 — event log: emit-time timestamps, append-only rendering
# --------------------------------------------------------------------------- #

def test_event_timestamps_are_set_at_emit_time_and_stable() -> None:
    engine = SimulationEngine()
    engine.log("first")
    engine.log("second")
    stamps = [e.time for e in engine.events]
    # Re-reading must not change stored timestamps (they are not recomputed).
    assert [e.time for e in engine.events] == stamps
    assert all(isinstance(s, str) and len(s) == 8 for s in stamps)  # HH:MM:SS


def test_log_messages_are_preserved_in_order() -> None:
    engine = SimulationEngine()
    engine.log("alpha")
    engine.log("beta")
    messages = [e.message for e in engine.events]
    assert messages[-2:] == ["alpha", "beta"]


class _RecordingLog:
    """Minimal stand-in for a NiceGUI log widget to test append-only logic."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def push(self, text: str) -> None:  # noqa: D401 - test double
        self.lines.append(text)


def test_append_events_is_append_only_across_renders() -> None:
    from amr_dashboard import panels

    engine = SimulationEngine()
    log = _RecordingLog()
    index = 0

    index = panels.append_events(log, engine, index)  # type: ignore[arg-type]
    first_count = len(log.lines)

    # Re-rendering without new events must not add lines.
    index = panels.append_events(log, engine, index)  # type: ignore[arg-type]
    assert len(log.lines) == first_count

    # One new event adds exactly one line.
    engine.log("a new event")
    index = panels.append_events(log, engine, index)  # type: ignore[arg-type]
    assert len(log.lines) == first_count + 1


# --------------------------------------------------------------------------- #
# F4 — START affordance and feedback
# --------------------------------------------------------------------------- #

def test_can_start_true_only_in_ready_with_valid_mission() -> None:
    engine = _engine_with_valid_mission()
    assert engine.can_start().allowed

    engine.start_mission()
    assert not engine.can_start().allowed  # RUNNING


def test_can_start_rejected_without_valid_mission() -> None:
    engine = SimulationEngine()  # no mission
    check = engine.can_start()
    assert not check.allowed
    assert "mission" in check.reason.lower()


def test_start_rejected_with_reason_in_disallowed_states() -> None:
    for state in (
        RobotState.BOOT,
        RobotState.DONE,
        RobotState.FAILED,
        RobotState.FAULT,
        RobotState.STOPPED,
    ):
        result = transition(state, Action.START)
        assert not result.allowed
        assert result.reason


# --------------------------------------------------------------------------- #
# Regression: existing behaviours remain intact
# --------------------------------------------------------------------------- #

def test_mission_edit_lock_remains_while_running() -> None:
    engine = _engine_with_valid_mission()
    assert engine.can_edit_mission()
    engine.start_mission()
    assert not engine.can_edit_mission()


def test_deterministic_tick_sequence_unchanged() -> None:
    def run() -> tuple[str, float]:
        engine = _engine_with_valid_mission()
        engine.start_mission()
        for _ in range(500):
            engine.tick(2.0)
            if engine.state is not RobotState.RUNNING:
                break
        return engine.state.value, round(engine.elapsed_s, 3)

    assert run() == run()
