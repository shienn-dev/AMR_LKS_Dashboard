"""Hardware-abstraction interfaces for the Lander robot (audit-phase design).

This module defines the *shapes* the dashboard uses to talk to robot hardware:
connection state, command/telemetry value objects, and the small protocols each
adapter implements. It performs **no I/O** — importing it never opens a serial
port, a camera device, or a servo bus.

Why the real transports are absent
----------------------------------
Audit findings (2026-10-16, on the school robot ``stematel-pi5``):

- No ROS 2 is installed, so the upstream ``/odom``, ``/cmd_vel`` and
  ``/kinematics`` interfaces do not exist here.
- The only candidate chassis/arm/IMU path is the STM32 board on
  ``/dev/ttyACM0`` (USB ``1a86:55d4``, matching the upstream
  ``ros_robot_controller``), but its serial protocol is unverified on the
  school's (ROBO JX-modified) board.
- The camera is a Deptrum Aurora 930 depth camera (USB ``3251:1930``) with no
  kernel driver bound, so it exposes no ``/dev/video`` node.

Per the project safety rules we ship only *offline* adapters that validate and
record commands but transmit nothing, plus honest availability probes. A real
transport is added only after the interface is verified on the hardware and a
supervised physical test is approved. See ``docs/robot_integration.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ConnectionState(str, Enum):
    """How the dashboard is connected to a robot subsystem.

    The default for every adapter is ``DISABLED`` (or ``UNAVAILABLE`` when a path
    is known to be missing): the UI must never claim a robot link it does not
    have.
    """

    DISABLED = "DISABLED"
    UNAVAILABLE = "UNAVAILABLE"
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"


@dataclass(frozen=True)
class ChassisCommand:
    """A velocity command in the robot body frame (SI units)."""

    linear_x: float = 0.0   # m/s, +forward
    linear_y: float = 0.0   # m/s, +left (mecanum only)
    angular_z: float = 0.0  # rad/s, +counter-clockwise

    def is_zero(self) -> bool:
        return self.linear_x == 0.0 and self.linear_y == 0.0 and self.angular_z == 0.0


@dataclass(frozen=True)
class ArmCommand:
    """A requested arm pose, in *device* units.

    ``positions`` are servo pulse-width units (upstream bus-servo range 0..1000)
    and ``duration_s`` is the move time. These values are carried through the
    adapter for validation only; the offline adapter never transmits them.
    """

    positions: tuple[int, ...] = ()
    duration_s: float = 1.0


@dataclass(frozen=True)
class CommandOutcome:
    """Result of submitting a command to an adapter.

    ``accepted`` = passed validation; ``transmitted`` = actually sent to
    hardware. For every adapter shipped in this phase ``transmitted`` is False.
    """

    accepted: bool
    transmitted: bool
    reason: str = ""


@dataclass(frozen=True)
class OdometrySample:
    """A single odometry reading (pose + velocity) with provenance."""

    x: float
    y: float
    yaw: float
    linear_x: float
    angular_z: float
    stamp_s: float
    source: str
    valid: bool = True


@dataclass(frozen=True)
class CameraStatus:
    """Availability of a camera source (never a fabricated frame)."""

    state: ConnectionState
    kind: str  # "none" | "usb" | "depth"
    device: str
    detail: str
    frames_available: bool


class ChassisAdapter(Protocol):
    """Interface the dashboard uses to drive the chassis (velocity control)."""

    name: str

    def state(self) -> ConnectionState: ...

    def last_command(self) -> ChassisCommand | None: ...

    def submit(self, command: ChassisCommand) -> CommandOutcome: ...

    def stop(self) -> CommandOutcome: ...


class ArmAdapter(Protocol):
    """Interface the dashboard uses to move the arm (joint-position control)."""

    name: str

    def state(self) -> ConnectionState: ...

    def last_command(self) -> ArmCommand | None: ...

    def submit(self, command: ArmCommand) -> CommandOutcome: ...

    def stop(self) -> CommandOutcome: ...


class OdometrySource(Protocol):
    """Interface the dashboard uses to read the robot pose."""

    name: str

    def state(self) -> ConnectionState: ...

    def detail(self) -> str: ...

    def sample(self) -> OdometrySample | None: ...
