"""Robot adapter registry tests (no device access)."""

from __future__ import annotations

from amr_core.robot.interfaces import ChassisCommand, ConnectionState
from amr_dashboard.robot_runtime import build_adapters, get_adapters, reset_adapters


def test_build_adapters_are_offline_and_safe() -> None:
    adapters = build_adapters()
    assert adapters.chassis.state() is ConnectionState.DISABLED
    assert adapters.arm.state() is ConnectionState.DISABLED
    assert adapters.odometry.state() is ConnectionState.UNAVAILABLE
    assert adapters.camera.frames_available is False
    assert adapters.estop.latched is False


def test_submitting_a_command_never_transmits() -> None:
    adapters = build_adapters()
    outcome = adapters.chassis.submit(ChassisCommand(0.1, 0.0, 0.0))
    assert outcome.transmitted is False


def test_get_adapters_is_a_singleton_until_reset() -> None:
    reset_adapters()
    first = get_adapters()
    assert get_adapters() is first
    reset_adapters()
    assert get_adapters() is not first
