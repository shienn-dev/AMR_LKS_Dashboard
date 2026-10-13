"""Operational state machine (architecture: "State machine operasional").

The robot only moves in RUNNING. The single way into RUNNING is one START press
while READY. DONE / FAILED / STOPPED return to READY through RESET.

A critical component failure is handled differently depending on *when* it
happens, following the PRD:

- Before a run (BOOT / READY): keep the robot out of service -> FAULT (OPS-02).
- During a run (RUNNING): stop the mission -> FAILED and name the component
  (OPS-11). This is a *software* simulation of stopping progression; it does
  NOT implement the physical emergency stop.

Phase 1 models a representative subset of the documented 7-state machine
(BOOT, READY, RUNNING, DONE, FAILED, FAULT). STOPPED is hardware e-stop driven
and out of scope for this prototype, but is kept in the enum so the state model
matches the design contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RobotState(str, Enum):
    """Operational states. Values are the strings shown to the operator."""

    BOOT = "BOOT"
    FAULT = "FAULT"
    READY = "READY"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class Action(str, Enum):
    """Actions that can drive a transition.

    These are *model* actions; the dashboard presents them as clearly-labelled
    software simulations, never as the physical buttons on the robot.
    """

    HEALTH_PASSED = "HEALTH_PASSED"      # boot completed health check OK
    HEALTH_FAILED = "HEALTH_FAILED"      # a critical component failed
    START = "START"                      # simulated START (one press when READY)
    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_FAILED = "MISSION_FAILED"
    RESET = "RESET"                      # simulated RESET
    ESTOP_PRESSED = "ESTOP_PRESSED"      # hardware e-stop signal (modeled)


@dataclass(frozen=True)
class TransitionResult:
    """Outcome of an attempted transition."""

    allowed: bool
    old_state: RobotState
    new_state: RobotState
    reason: str = ""

    @property
    def changed(self) -> bool:
        return self.old_state is not self.new_state


# Explicit allowed transitions: (current_state, action) -> next_state.
# Anything not listed here is rejected. This keeps the state model testable and
# prevents arbitrary UI-only state changes.
_TRANSITIONS: dict[tuple[RobotState, Action], RobotState] = {
    (RobotState.BOOT, Action.HEALTH_PASSED): RobotState.READY,
    (RobotState.BOOT, Action.HEALTH_FAILED): RobotState.FAULT,
    (RobotState.READY, Action.START): RobotState.RUNNING,
    (RobotState.READY, Action.HEALTH_FAILED): RobotState.FAULT,
    (RobotState.RUNNING, Action.MISSION_COMPLETED): RobotState.DONE,
    (RobotState.RUNNING, Action.MISSION_FAILED): RobotState.FAILED,
    (RobotState.RUNNING, Action.ESTOP_PRESSED): RobotState.STOPPED,
    # A critical component failing DURING a run stops the mission: PRD OPS-11
    # says the robot stops and the mission goes FAILED (distinct from the
    # pre-run health check, which goes FAULT per OPS-02). The failed component
    # is recorded in the engine event log.
    (RobotState.RUNNING, Action.HEALTH_FAILED): RobotState.FAILED,
    # Recovery path: DONE / FAILED / STOPPED -> READY only through RESET.
    (RobotState.DONE, Action.RESET): RobotState.READY,
    (RobotState.FAILED, Action.RESET): RobotState.READY,
    (RobotState.STOPPED, Action.RESET): RobotState.READY,
    # FAULT is cleared only after recovery conditions are checked by the caller.
    (RobotState.FAULT, Action.RESET): RobotState.READY,
}

# States in which mission editing must be locked (architecture / DASH-05).
_LOCKED_STATES: frozenset[RobotState] = frozenset({RobotState.RUNNING})

# States that require an explicit RESET to leave.
TERMINAL_STATES: frozenset[RobotState] = frozenset(
    {RobotState.DONE, RobotState.FAILED, RobotState.STOPPED, RobotState.FAULT}
)


def transition(current: RobotState, action: Action) -> TransitionResult:
    """Return the result of applying *action* in *current* state.

    Never raises: an illegal action yields ``allowed=False`` and the same state.
    """
    target = _TRANSITIONS.get((current, action))
    if target is None:
        return TransitionResult(
            allowed=False,
            old_state=current,
            new_state=current,
            reason=f"action {action.value} is not allowed in state {current.value}",
        )
    return TransitionResult(allowed=True, old_state=current, new_state=target)


def can_edit_mission(state: RobotState) -> bool:
    """Mission editing is locked while RUNNING (DASH-05)."""
    return state not in _LOCKED_STATES
