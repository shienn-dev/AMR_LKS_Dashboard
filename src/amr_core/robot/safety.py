"""Command safety: speed limiting, input validation and a software E-stop.

Everything here is pure computation — no device access. It is used by the offline
adapters (and, later, by any verified transport) so a command can never leave the
software with a non-finite value or beyond the configured speed limits.

Note: the *hardware* E-stop is a physical button on the robot. The
:class:`EStopLatch` here is a software stop the operator triggers from the
dashboard; it is **not** a substitute for the physical button.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from amr_core.robot.interfaces import ArmCommand, ChassisCommand

# Upstream bus-servo units clamp to 0..1000 and duration to 0.02..30 s
# (source: Hiwonder/LanderPi servo_controller.py — SOURCE-ONLY, not verified on
# the school board). We use these only to *reject* bad input; nothing is sent.
ARM_PULSE_MIN = 0
ARM_PULSE_MAX = 1000
ARM_DURATION_MIN_S = 0.02
ARM_DURATION_MAX_S = 30.0


@dataclass(frozen=True)
class SpeedLimits:
    """Maximum chassis velocities the dashboard will ever validate (SI units)."""

    max_linear_x: float = 0.19
    max_linear_y: float = 0.30
    max_angular_z: float = 1.20

    def clamp(self, command: ChassisCommand) -> ChassisCommand:
        return ChassisCommand(
            linear_x=_clamp(command.linear_x, self.max_linear_x),
            linear_y=_clamp(command.linear_y, self.max_linear_y),
            angular_z=_clamp(command.angular_z, self.max_angular_z),
        )


def _clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def validate_chassis_command(
    command: ChassisCommand, limits: SpeedLimits
) -> tuple[ChassisCommand | None, str]:
    """Return ``(clamped_command, "")`` or ``(None, reason)``.

    Non-finite values (NaN/Inf) are rejected outright; finite values are clamped
    to *limits*.
    """
    for field_name, value in (
        ("linear_x", command.linear_x),
        ("linear_y", command.linear_y),
        ("angular_z", command.angular_z),
    ):
        if not math.isfinite(value):
            return None, f"{field_name} is not a finite number"
    return limits.clamp(command), ""


def validate_arm_command(command: ArmCommand) -> tuple[ArmCommand | None, str]:
    """Validate and clamp an arm command.

    Returns ``(clamped_command, "")`` or ``(None, reason)``. Pulse widths are
    clamped to ``ARM_PULSE_MIN..ARM_PULSE_MAX`` and the duration to
    ``ARM_DURATION_MIN_S..ARM_DURATION_MAX_S``.
    """
    if not math.isfinite(command.duration_s):
        return None, "duration_s is not a finite number"
    positions: list[int] = []
    for index, value in enumerate(command.positions):
        if isinstance(value, bool) or not isinstance(value, int):
            return None, f"position[{index}] must be an integer"
        positions.append(max(ARM_PULSE_MIN, min(ARM_PULSE_MAX, value)))
    duration = max(ARM_DURATION_MIN_S, min(ARM_DURATION_MAX_S, command.duration_s))
    return ArmCommand(positions=tuple(positions), duration_s=duration), ""


class EStopLatch:
    """A software stop latch (not the physical E-stop).

    ``trip`` latches; ``clear`` only succeeds when the caller explicitly confirms
    it is safe, so a stray click cannot silently re-enable motion.
    """

    def __init__(self) -> None:
        self._latched = False
        self._reason = ""

    @property
    def latched(self) -> bool:
        return self._latched

    @property
    def reason(self) -> str:
        return self._reason

    def trip(self, reason: str = "") -> None:
        self._latched = True
        self._reason = reason

    def clear(self, *, confirmed_safe: bool) -> bool:
        if not confirmed_safe:
            return False
        self._latched = False
        self._reason = ""
        return True
