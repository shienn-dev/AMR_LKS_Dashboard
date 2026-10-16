"""Unit tests for command safety (speed limiting, validation, software E-stop).

Pure-software tests: no hardware, no serial port, no servo bus.
"""

from __future__ import annotations

import math

from amr_core.robot.interfaces import ArmCommand, ChassisCommand
from amr_core.robot.safety import (
    EStopLatch,
    SpeedLimits,
    validate_arm_command,
    validate_chassis_command,
)


def test_clamps_to_limits() -> None:
    limits = SpeedLimits(max_linear_x=0.3, max_linear_y=0.3, max_angular_z=1.2)
    clamped, reason = validate_chassis_command(ChassisCommand(5.0, -5.0, 9.0), limits)
    assert reason == ""
    assert clamped == ChassisCommand(0.3, -0.3, 1.2)


def test_within_limits_is_unchanged() -> None:
    limits = SpeedLimits()
    clamped, reason = validate_chassis_command(ChassisCommand(0.1, 0.0, -0.2), limits)
    assert reason == ""
    assert clamped == ChassisCommand(0.1, 0.0, -0.2)


def test_rejects_non_finite() -> None:
    limits = SpeedLimits()
    for bad in (math.nan, math.inf, -math.inf):
        clamped, reason = validate_chassis_command(ChassisCommand(bad, 0.0, 0.0), limits)
        assert clamped is None
        assert "finite" in reason


def test_arm_clamps_pulse_and_duration() -> None:
    command, reason = validate_arm_command(ArmCommand(positions=(-5, 2000, 500), duration_s=99.0))
    assert reason == ""
    assert command is not None
    assert command.positions == (0, 1000, 500)
    assert command.duration_s == 30.0


def test_arm_rejects_non_integer_and_non_finite_duration() -> None:
    bad_command = ArmCommand(positions=(1.5,), duration_s=1.0)  # type: ignore[arg-type]
    bad, reason = validate_arm_command(bad_command)
    assert bad is None
    assert "integer" in reason

    bad, reason = validate_arm_command(ArmCommand(positions=(1,), duration_s=math.nan))
    assert bad is None
    assert "finite" in reason


def test_estop_latch_requires_confirmation_to_clear() -> None:
    latch = EStopLatch()
    assert not latch.latched

    latch.trip("operator")
    assert latch.latched
    assert latch.reason == "operator"

    assert latch.clear(confirmed_safe=False) is False
    assert latch.latched

    assert latch.clear(confirmed_safe=True) is True
    assert not latch.latched
    assert latch.reason == ""
