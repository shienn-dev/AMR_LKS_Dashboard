"""Process-wide robot adapters for the dashboard (audit phase).

Builds the safe, offline adapter set once per process. Nothing here opens a
device. Adapters are shared by every browser page, mirroring the LiDAR runtime.

Design note: the dashboard UI depends only on the adapter *interfaces*
(``amr_core.robot.interfaces``), never on a concrete transport. Swapping an
offline adapter for a verified one is a small change here once the interface is
verified on the hardware and a supervised physical test is approved.
"""

from __future__ import annotations

from dataclasses import dataclass

from amr_core.robot.arm import OfflineArmAdapter
from amr_core.robot.camera import probe_camera
from amr_core.robot.chassis import OfflineChassisAdapter
from amr_core.robot.interfaces import CameraStatus
from amr_core.robot.odometry import NoOdometrySource
from amr_core.robot.safety import EStopLatch, SpeedLimits

_ODOMETRY_DETAIL = (
    "No odometry source active: no ROS 2 /odom node is running, and the STM32 "
    "encoder/IMU path on /dev/ttyACM0 is unverified. See docs/robot_integration.md."
)


@dataclass
class RobotAdapters:
    """The process-wide set of robot adapters (offline / safe)."""

    chassis: OfflineChassisAdapter
    arm: OfflineArmAdapter
    odometry: NoOdometrySource
    camera: CameraStatus
    estop: EStopLatch


def build_adapters() -> RobotAdapters:
    """Create a fresh adapter set. Safe to call in tests (no device access)."""
    return RobotAdapters(
        chassis=OfflineChassisAdapter(limits=SpeedLimits()),
        arm=OfflineArmAdapter(),
        odometry=NoOdometrySource(_ODOMETRY_DETAIL),
        camera=probe_camera(),
        estop=EStopLatch(),
    )


_adapters: RobotAdapters | None = None


def get_adapters() -> RobotAdapters:
    """Return the process-wide adapter set, creating it on first use."""
    global _adapters
    if _adapters is None:
        _adapters = build_adapters()
    return _adapters


def reset_adapters() -> None:
    """Drop the process-wide adapter set (test helper)."""
    global _adapters
    _adapters = None
