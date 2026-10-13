"""Tests for the operational state machine (allowed/rejected transitions)."""

from __future__ import annotations

from amr_core.states import Action, RobotState, can_edit_mission, transition


def test_ready_to_running_via_start() -> None:
    result = transition(RobotState.READY, Action.START)
    assert result.allowed
    assert result.new_state is RobotState.RUNNING


def test_running_to_done() -> None:
    result = transition(RobotState.RUNNING, Action.MISSION_COMPLETED)
    assert result.allowed
    assert result.new_state is RobotState.DONE


def test_running_to_failed() -> None:
    result = transition(RobotState.RUNNING, Action.MISSION_FAILED)
    assert result.allowed
    assert result.new_state is RobotState.FAILED


def test_ready_to_fault_on_critical_health_failure() -> None:
    result = transition(RobotState.READY, Action.HEALTH_FAILED)
    assert result.allowed
    assert result.new_state is RobotState.FAULT


def test_cannot_start_when_not_ready() -> None:
    for state in (RobotState.BOOT, RobotState.RUNNING, RobotState.DONE, RobotState.FAULT):
        result = transition(state, Action.START)
        assert not result.allowed
        assert result.new_state is state


def test_failed_returns_ready_only_via_reset() -> None:
    # Any action other than RESET is rejected from FAILED.
    for action in (Action.START, Action.HEALTH_PASSED, Action.MISSION_COMPLETED):
        assert not transition(RobotState.FAILED, action).allowed
    result = transition(RobotState.FAILED, Action.RESET)
    assert result.allowed
    assert result.new_state is RobotState.READY


def test_done_and_stopped_return_ready_via_reset() -> None:
    assert transition(RobotState.DONE, Action.RESET).new_state is RobotState.READY
    assert transition(RobotState.STOPPED, Action.RESET).new_state is RobotState.READY


def test_running_estop_goes_stopped() -> None:
    result = transition(RobotState.RUNNING, Action.ESTOP_PRESSED)
    assert result.allowed
    assert result.new_state is RobotState.STOPPED


def test_rejected_transition_reports_reason() -> None:
    result = transition(RobotState.BOOT, Action.START)
    assert not result.allowed
    assert result.reason


def test_mission_editing_locked_only_while_running() -> None:
    assert not can_edit_mission(RobotState.RUNNING)
    for state in (
        RobotState.BOOT,
        RobotState.READY,
        RobotState.DONE,
        RobotState.FAILED,
        RobotState.FAULT,
    ):
        assert can_edit_mission(state)
