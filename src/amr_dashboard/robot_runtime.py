"""Process-wide robot adapters for the dashboard.

Builds the adapter set once per process. Nothing here opens a device unless
the operator explicitly asked for a **live** chassis: the default is the
offline adapter set, which validates and records commands but transmits
nothing.

The live chassis is opt-in through ``--chassis-live`` on the command line.
That flag is the only thing that can turn a real robot into a moving robot, so
it is deliberately not implied by anything else -- not by the port name, not by
an environment variable, not by the presence of the device.

Design note: the dashboard UI depends only on the adapter *interfaces*
(``amr_core.robot.interfaces``), never on a concrete transport.
"""

from __future__ import annotations

from dataclasses import dataclass

from amr_core.robot.arm import OfflineArmAdapter
from amr_core.robot.camera import probe_camera
from amr_core.robot.chassis import OfflineChassisAdapter
from amr_core.robot.interfaces import CameraStatus, ChassisAdapter, ConnectionState
from amr_core.robot.motion_guard import MotionGuard
from amr_core.robot.odometry import NoOdometrySource
from amr_core.robot.safety import EStopLatch, SpeedLimits
from amr_core.robot.serial_chassis import DEFAULT_PORT, SerialChassisAdapter
from amr_dashboard.chassis_transport import open_serial_port

_ODOMETRY_DETAIL = (
    "No odometry source active: no ROS 2 /odom node is running, and the STM32 "
    "encoder/IMU path on /dev/ttyACM0 is unverified. See docs/robot_integration.md."
)

#: Speed limits used by the live chassis. ``max_linear_x`` is the highest speed
#: ever measured on this robot (0,19 m/s). The lateral and rotation limits are
#: deliberately much lower than the defaults in ``safety.py`` until they have
#: been measured on the floor.
LIVE_LIMITS = SpeedLimits(
    max_linear_x=0.19,
    max_linear_y=0.05,
    max_angular_z=0.20,
)


@dataclass
class RobotAdapters:
    """The process-wide set of robot adapters (offline / safe)."""

    chassis: ChassisAdapter
    arm: OfflineArmAdapter
    odometry: NoOdometrySource
    camera: CameraStatus
    estop: EStopLatch
    guard: MotionGuard | None = None
    live: bool = False


def build_adapters(*, live: bool = False, port: str = DEFAULT_PORT) -> RobotAdapters:
    """Create a fresh adapter set.

    ``live=False`` (the default) never touches a device. ``live=True`` opens
    the STM32 serial port and installs the motion guard; the caller is
    responsible for closing it again (the dashboard does that on shutdown).
    """
    if live:
        guard = MotionGuard()
        chassis: ChassisAdapter = SerialChassisAdapter(
            port=port,
            limits=LIVE_LIMITS,
            guard=guard,
            port_factory=open_serial_port,
        )
    else:
        guard = None
        chassis = OfflineChassisAdapter(limits=SpeedLimits())
    return RobotAdapters(
        chassis=chassis,
        arm=OfflineArmAdapter(),
        odometry=NoOdometrySource(_ODOMETRY_DETAIL),
        camera=probe_camera(),
        estop=EStopLatch(),
        guard=guard,
        live=live,
    )


_adapters: RobotAdapters | None = None


def get_adapters() -> RobotAdapters:
    """Return the process-wide adapter set, creating it on first use."""
    global _adapters
    if _adapters is None:
        _adapters = build_adapters()
    return _adapters


def configure(*, live: bool = False, port: str = DEFAULT_PORT) -> RobotAdapters:
    """Install the adapter set the operator asked for (replaces any earlier one)."""
    global _adapters
    close_adapters()
    _adapters = build_adapters(live=live, port=port)
    return _adapters


def close_adapters() -> None:
    """Close the live chassis port, if there is one."""
    global _adapters
    if _adapters is None:
        return
    chassis = _adapters.chassis
    if hasattr(chassis, "close"):
        chassis.close()  # type: ignore[attr-defined]


def open_live_chassis() -> ConnectionState:
    """Open the live chassis port, if the live adapter is installed.

    Returns the resulting connection state; the offline adapter reports
    ``DISABLED`` and nothing is opened.
    """
    adapters = get_adapters()
    opener = getattr(adapters.chassis, "open", None)
    if opener is None:
        return ConnectionState.DISABLED
    return opener()


def reset_adapters() -> None:
    """Drop the process-wide adapter set (test helper)."""
    global _adapters
    close_adapters()
    _adapters = None
