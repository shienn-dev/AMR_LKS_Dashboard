"""Odometry sources.

No odometry source is verified on the school robot: there is no ROS 2 ``/odom``
node running and no verified encoder/IMU read path. :class:`NoOdometrySource`
therefore reports ``UNAVAILABLE`` and returns no sample — the dashboard must
never invent a pose. The ``OdometrySource`` protocol and :func:`validate_sample`
are provided so a real source can be plugged in once it is verified.

Odometry *type* matters: wheel/encoder odometry (upstream uses encoder odometry
fused with IMU via an EKF), visual odometry, and laser odometry are different
sources with different error characteristics. Nothing here should be labelled
"hardware odometry" until a real source is verified on the device.
"""

from __future__ import annotations

import math

from amr_core.robot.interfaces import ConnectionState, OdometrySample


def validate_sample(sample: OdometrySample) -> tuple[bool, str]:
    """Return ``(True, "")`` if every numeric field is finite, else ``(False, reason)``."""
    for field_name, value in (
        ("x", sample.x),
        ("y", sample.y),
        ("yaw", sample.yaw),
        ("linear_x", sample.linear_x),
        ("angular_z", sample.angular_z),
        ("stamp_s", sample.stamp_s),
    ):
        if not math.isfinite(value):
            return False, f"{field_name} is not a finite number"
    return True, ""


class NoOdometrySource:
    """Honest 'no odometry' source: always UNAVAILABLE, never a sample."""

    name = "none"

    def __init__(self, detail: str = "No odometry source is available.") -> None:
        self._detail = detail

    def state(self) -> ConnectionState:
        return ConnectionState.UNAVAILABLE

    def detail(self) -> str:
        return self._detail

    def sample(self) -> OdometrySample | None:
        return None
