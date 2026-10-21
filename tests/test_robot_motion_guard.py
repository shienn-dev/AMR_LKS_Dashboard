"""Motion guard tests: the fail-safe layer of hold-to-move (no hardware).

These are the tests that decide whether a lost "release" event can leave the
robot driving. The clock is injected, so every timing case is deterministic.
"""

from __future__ import annotations

from amr_core.robot.interfaces import ChassisCommand
from amr_core.robot.motion_guard import MotionGuard


class FakeClock:
    """A clock that only moves when the test tells it to."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _armed_guard(timeout: float = 0.3) -> tuple[MotionGuard, FakeClock]:
    clock = FakeClock()
    guard = MotionGuard(heartbeat_timeout_s=timeout, clock=clock)
    assert guard.arm("session-a") is True
    guard.heartbeat("session-a")
    return guard, clock


def test_only_one_session_may_hold_control() -> None:
    guard, _clock = _armed_guard()
    assert guard.arm("session-b") is False
    assert guard.lease_owner == "session-a"


def test_motion_requires_the_lease() -> None:
    guard, _clock = _armed_guard()
    assert guard.request_motion("session-b", ChassisCommand(0.1, 0, 0)) is False
    assert guard.command() is None


def test_motion_is_accepted_while_the_heartbeat_is_fresh() -> None:
    guard, clock = _armed_guard()
    clock.advance(0.1)
    assert guard.request_motion("session-a", ChassisCommand(0.1, 0, 0)) is True
    assert guard.poll() == ChassisCommand(0.1, 0, 0)


def test_a_lost_heartbeat_stops_the_robot() -> None:
    """The browser died, the tab was closed, the network dropped: stop."""
    guard, clock = _armed_guard(timeout=0.3)
    assert guard.request_motion("session-a", ChassisCommand(0.1, 0, 0)) is True
    clock.advance(0.31)
    assert guard.poll() is None
    assert guard.stopped_reason == "heartbeat lost"


def test_motion_is_refused_when_the_heartbeat_is_already_stale() -> None:
    guard, clock = _armed_guard(timeout=0.3)
    clock.advance(0.5)
    assert guard.request_motion("session-a", ChassisCommand(0.1, 0, 0)) is False
    assert guard.command() is None


def test_a_renewed_heartbeat_keeps_the_motion_alive() -> None:
    guard, clock = _armed_guard(timeout=0.3)
    assert guard.request_motion("session-a", ChassisCommand(0.1, 0, 0)) is True
    for _ in range(10):
        clock.advance(0.1)
        guard.heartbeat("session-a")
        assert guard.poll() is not None


def test_a_heartbeat_from_another_session_does_not_keep_the_robot_alive() -> None:
    guard, clock = _armed_guard(timeout=0.3)
    assert guard.request_motion("session-a", ChassisCommand(0.1, 0, 0)) is True
    clock.advance(0.2)
    assert guard.heartbeat("session-b") is False
    clock.advance(0.15)
    assert guard.poll() is None


def test_releasing_the_button_stops_the_motion() -> None:
    guard, _clock = _armed_guard()
    assert guard.request_motion("session-a", ChassisCommand(0.1, 0, 0)) is True
    guard.release_motion("session-a")
    assert guard.poll() is None
    assert guard.stopped_reason == "button released"


def test_the_software_estop_stops_and_refuses_new_motion() -> None:
    guard, _clock = _armed_guard()
    guard.trip("operator")
    assert guard.latched is True
    assert guard.poll() is None
    assert guard.request_motion("session-a", ChassisCommand(0.1, 0, 0)) is False
    assert "e-stop latched" in guard.stopped_reason


def test_clearing_the_estop_needs_an_explicit_confirmation() -> None:
    guard, _clock = _armed_guard()
    guard.trip("operator")
    assert guard.clear(confirmed_safe=False) is False
    assert guard.latched is True
    assert guard.clear(confirmed_safe=True) is True
    assert guard.latched is False


def test_disarming_releases_the_lease() -> None:
    guard, _clock = _armed_guard()
    assert guard.disarm("session-a") is True
    assert guard.lease_owner is None
    assert guard.disarm("session-a") is False


def test_reset_motion_clears_the_command_but_keeps_the_lease() -> None:
    guard, _clock = _armed_guard()
    assert guard.request_motion("session-a", ChassisCommand(0.1, 0, 0)) is True
    guard.reset_motion()
    assert guard.command() is None
    assert guard.lease_owner == "session-a"
