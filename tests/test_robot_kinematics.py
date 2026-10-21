"""Mecanum kinematics tests (pure computation, no hardware).

The assertions that matter are the ones tied to facts measured on this robot:

* the forward command must produce the pattern that was verified on the floor
  (``1:- 2:- 3:+ 4:+``);
* turning in place must produce the same sign on all four motors, which is
  what was observed when a uniform command was run (sesi 2 §9.5);
* the scale must land on the operating point that was actually measured
  (u = 1,0 rps gave 0,19 m/s);
* no command may ever exceed the highest rate ever measured.
"""

from __future__ import annotations

import pytest

from amr_core.robot import kinematics as k


def _pattern(pairs: list[tuple[int, float]]) -> tuple[int, ...]:
    return tuple(1 if rate >= 0 else -1 for _motor_id, rate in pairs)


def test_forward_matches_the_pattern_verified_on_the_floor() -> None:
    pairs = k.command_for_body_velocity(0.19, 0.0, 0.0)
    assert _pattern(pairs) == (-1, -1, 1, 1)
    assert [motor_id for motor_id, _ in pairs] == [1, 2, 3, 4]


def test_backward_is_the_inverse_of_forward() -> None:
    forward = k.command_for_body_velocity(0.19, 0.0, 0.0)
    backward = k.command_for_body_velocity(-0.19, 0.0, 0.0)
    assert _pattern(backward) == tuple(-sign for sign in _pattern(forward))


def test_turning_in_place_uses_the_same_sign_on_all_four_motors() -> None:
    """Matches the hardware observation: a uniform command spins the robot."""
    pairs = k.command_for_body_velocity(0.0, 0.0, 1.0)
    assert _pattern(pairs) == (1, 1, 1, 1)
    reverse = k.command_for_body_velocity(0.0, 0.0, -1.0)
    assert _pattern(reverse) == (-1, -1, -1, -1)


def test_strafe_splits_the_wheels_into_two_diagonals() -> None:
    pairs = k.command_for_body_velocity(0.0, 0.19, 0.0)
    signs = _pattern(pairs)
    assert signs[0] == signs[2]
    assert signs[1] == signs[3]
    assert signs[0] != signs[1]


def test_strafe_left_drives_the_robot_left() -> None:
    """Verified on the floor on 2026-10-21: left and right were swapped.

    The first version of the model had the lateral axis mirrored, and the robot
    drove the wrong way. This test locks the corrected pattern so it cannot
    silently flip back.
    """
    left = k.command_for_body_velocity(0.0, 0.19, 0.0)
    right = k.command_for_body_velocity(0.0, -0.19, 0.0)
    assert _pattern(left) == (1, -1, 1, -1)
    assert _pattern(right) == (-1, 1, -1, 1)
    assert k.LATERAL_SIGN == -1.0


def test_the_lateral_flip_does_not_touch_forward_or_yaw() -> None:
    """Only the lateral axis may be mirrored; forward and yaw are verified."""
    assert _pattern(k.command_for_body_velocity(0.19, 0.0, 0.0)) == (-1, -1, 1, 1)
    assert _pattern(k.command_for_body_velocity(0.0, 0.0, 1.0)) == (1, 1, 1, 1)
    assert _pattern(k.command_for_body_velocity(0.0, 0.0, -1.0)) == (-1, -1, -1, -1)


def test_zero_command_stops_every_wheel() -> None:
    pairs = k.command_for_body_velocity(0.0, 0.0, 0.0)
    assert all(rate == 0.0 for _motor_id, rate in pairs)


def test_scale_lands_on_the_measured_operating_point() -> None:
    """u = 1,0 rps measured 0,19 m/s; 0,19 m/s must map back to that rate."""
    assert k.command_for_speed(0.19) == pytest.approx(1.036, abs=0.005)
    assert k.command_for_speed(0.06) == pytest.approx(0.327, abs=0.005)


def test_no_command_exceeds_the_highest_rate_ever_measured() -> None:
    """A diagonal needs more wheel rate than a straight command of the same size."""
    diagonal = k.command_for_body_velocity(0.19, 0.19, 0.0)
    assert max(abs(rate) for _motor_id, rate in diagonal) == pytest.approx(
        k.MAX_TESTED_RPS
    )
    for command in (
        (0.19, 0.0, 0.0),
        (0.0, 0.19, 0.0),
        (0.19, 0.19, 0.19),
        (0.0, 0.0, 1.0),
    ):
        pairs = k.command_for_body_velocity(*command)
        assert max(abs(rate) for _motor_id, rate in pairs) <= k.MAX_TESTED_RPS + 1e-9


def test_clamping_scales_the_whole_command_and_keeps_its_direction() -> None:
    commands = {"front_left": 2.0, "rear_left": -2.0, "front_right": 0.0, "rear_right": 0.0}
    clamped = k.clamp_to_max_rate(commands, max_rate_rps=1.0)
    assert clamped["front_left"] == pytest.approx(1.0)
    assert clamped["rear_left"] == pytest.approx(-1.0)
    assert clamped["front_right"] == 0.0


def test_clamping_leaves_commands_below_the_limit_alone() -> None:
    commands = {"front_left": 0.5, "rear_left": -0.5}
    assert k.clamp_to_max_rate(commands, max_rate_rps=1.0) == commands


def test_stall_threshold_helper() -> None:
    assert k.is_above_stall_threshold(0.3) is True
    assert k.is_above_stall_threshold(0.27) is False
    assert k.is_above_stall_threshold(-0.3) is True


def test_command_for_speed_rejects_nonsense() -> None:
    with pytest.raises(ValueError):
        k.command_for_speed(0.1, c_eff_m=0.0)
    with pytest.raises(ValueError):
        k.command_for_speed(0.1, efficiency=0.0)


def test_direction_report_covers_every_direction() -> None:
    lines = k.direction_report()
    assert len(lines) == 8
    assert "1:-  2:-  3:+  4:+" in lines[0]
