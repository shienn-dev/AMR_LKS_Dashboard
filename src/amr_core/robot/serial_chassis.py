"""Serial chassis adapter: drives the STM32 board over ``/dev/ttyACM0``.

This is the transport that the dashboard has been missing. It replaces the
placeholder that refused to transmit. What it does, and why each part is
there:

* **It owns the port in a background thread.** Exactly one writer, so two
  commands can never interleave bytes on the wire.
* **It streams, it does not blip.** The board's firmware stops the motors when
  the command stream stops (verified on hardware, sesi 2 §9.3: one frame
  produced only a twitch). So the adapter keeps sending the current command at
  ``rate_hz`` (50 Hz, the rate that was measured to be smooth) and the
  :class:`~amr_core.robot.motion_guard.MotionGuard` decides *what* to send.
* **It always sends a stop frame.** On ``stop()``, on close and in a
  ``finally`` block, so the robot is never left with a live command.
* **It reports its state honestly.** ``CONNECTED`` only while the port is
  really open and the stream thread is alive.
* **It never exceeds the tested envelope.** The body command is clamped by
  :mod:`amr_core.robot.safety` and then converted to wheel rates by
  :mod:`amr_core.robot.kinematics`, which caps the rate at the highest value
  ever measured on this robot.

Safety
------
The adapter is only useful with a human next to the robot. The physical
E-stop remains the primary stop; the software guard only decides what the
stream contains.

No device imports
------------------
This module does not import pyserial, and it is not allowed to: the
``amr_core.robot`` package stays free of device code (there is a guard test
for it). The port is opened by whoever constructs the adapter, through the
``port_factory`` argument -- the dashboard passes
:func:`amr_dashboard.chassis_transport.open_serial_port`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from amr_core.robot.interfaces import ChassisCommand, CommandOutcome, ConnectionState
from amr_core.robot.kinematics import (
    DEFAULT_MODEL,
    MecanumModel,
    command_for_body_velocity,
)
from amr_core.robot.motion_guard import MotionGuard
from amr_core.robot.safety import SpeedLimits, validate_chassis_command
from amr_core.robot.stm32_protocol import build_motor_frame

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 1_000_000
DEFAULT_RATE_HZ = 50.0
#: Seconds to wait after opening the port before the first frame. The board
#: needs a moment after a USB CDC open.
DEFAULT_SETTLE_S = 0.3

#: How many stop frames are sent when a command ends, before the stream goes
#: quiet. A burst makes the stop explicit; after that the board's watchdog
#: holds the motors off, so the robot does not hum while idle.
STOP_FRAME_BURST = 3


class SerialPort(Protocol):
    """The small part of ``serial.Serial`` this adapter needs."""

    def write(self, data: bytes, /) -> int | None: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


@dataclass
class SerialChassisStats:
    """Counters for the dashboard's state panel."""

    frames_sent: int = 0
    frames_failed: int = 0
    last_error: str = ""
    last_frame_at: float = 0.0
    port_opened_at: float = 0.0


class SerialChassisAdapter:
    """Drives the chassis over a serial port. One writer, one stream."""

    name = "serial"

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        limits: SpeedLimits | None = None,
        *,
        baud: int = DEFAULT_BAUD,
        rate_hz: float = DEFAULT_RATE_HZ,
        settle_s: float = DEFAULT_SETTLE_S,
        guard: MotionGuard | None = None,
        model: MecanumModel = DEFAULT_MODEL,
        port_factory: Callable[[str, int], SerialPort] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.port = port
        self.baud = baud
        self.rate_hz = rate_hz
        self.settle_s = settle_s
        self.limits = limits if limits is not None else SpeedLimits()
        self.guard = guard if guard is not None else MotionGuard()
        self.model = model
        self._port_factory = port_factory
        self._clock = clock
        self._port: SerialPort | None = None
        self._thread: threading.Thread | None = None
        self._closing = threading.Event()
        self._lock = threading.Lock()
        self._state = ConnectionState.DISABLED
        self._last: ChassisCommand | None = None
        self.stats = SerialChassisStats()

    # --- lifecycle --------------------------------------------------------- #

    def open(self) -> ConnectionState:
        """Open the port and start the streaming thread."""
        with self._lock:
            if self._state == ConnectionState.CONNECTED:
                return self._state
            if self._port_factory is None:
                self._state = ConnectionState.UNAVAILABLE
                self.stats.last_error = "no port factory was given"
                return self._state
            try:
                self._port = self._port_factory(self.port, self.baud)
            except Exception as exc:  # noqa: BLE001 - report the real cause
                self._state = ConnectionState.UNAVAILABLE
                self.stats.last_error = f"{type(exc).__name__}: {exc}"
                return self._state
            self.stats.port_opened_at = self._clock()
            self._state = ConnectionState.CONNECTED
            # A command left over from a previous session must never start the
            # robot moving by itself.
            self.guard.reset_motion()
            self._closing.clear()
            self._thread = threading.Thread(
                target=self._stream_loop, name="chassis-stream", daemon=True
            )
            self._thread.start()
        return self._state

    def close(self) -> None:
        """Stop the stream, send a final stop frame and close the port."""
        self._closing.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            self._thread = None
            port = self._port
            self._port = None
            self._state = ConnectionState.DISABLED
        if port is not None:
            try:
                port.write(self._stop_frame())
                port.flush()
            except Exception as exc:  # noqa: BLE001
                self.stats.last_error = f"stop frame failed: {exc}"
            finally:
                try:
                    port.close()
                except Exception as exc:  # noqa: BLE001
                    self.stats.last_error = f"close failed: {exc}"

    # --- adapter interface -------------------------------------------------- #

    def state(self) -> ConnectionState:
        return self._state

    def last_command(self) -> ChassisCommand | None:
        return self._last

    def submit(self, command: ChassisCommand, *, session_id: str | None = None) -> CommandOutcome:
        """Validate, clamp and start streaming ``command``.

        When ``session_id`` is given, the motion guard has to agree first: the
        guard owns the lease, the heartbeat and the software E-stop, so it is
        the only thing allowed to decide that the robot may move.
        """
        clamped, reason = validate_chassis_command(command, self.limits)
        if clamped is None:
            return CommandOutcome(accepted=False, transmitted=False, reason=reason)
        self._last = clamped
        if session_id is not None:
            if not self.guard.request_motion(session_id, clamped):
                return CommandOutcome(
                    accepted=False,
                    transmitted=False,
                    reason=self.guard.stopped_reason or "motion refused by the guard",
                )
        if self._state != ConnectionState.CONNECTED:
            return CommandOutcome(
                accepted=True,
                transmitted=False,
                reason="validated; the chassis port is not connected",
            )
        return CommandOutcome(
            accepted=True,
            transmitted=True,
            reason=f"streaming {self._describe(clamped)}",
        )

    def stop(self) -> CommandOutcome:
        """Stop the robot now."""
        self._last = ChassisCommand()
        self.guard.release_motion(self.guard.lease_owner or "")
        if self._state != ConnectionState.CONNECTED:
            return CommandOutcome(
                accepted=True,
                transmitted=False,
                reason="stop requested; the chassis port is not connected",
            )
        self._write(self._stop_frame())
        return CommandOutcome(accepted=True, transmitted=True, reason="stop frame sent")

    # --- internals ---------------------------------------------------------- #

    def _describe(self, command: ChassisCommand) -> str:
        return (
            f"vx={command.linear_x:.3f} m/s, vy={command.linear_y:.3f} m/s, "
            f"wz={command.angular_z:.3f} rad/s"
        )

    def _stop_frame(self) -> bytes:
        return build_motor_frame([(motor_id, 0.0) for motor_id in (1, 2, 3, 4)])

    def _frame_for(self, command: ChassisCommand) -> bytes:
        # Clamp again on the way to the wire: the guard may hold a command the
        # safety limits would refuse, and the limits are the last word.
        clamped, _ = validate_chassis_command(command, self.limits)
        effective = clamped if clamped is not None else ChassisCommand()
        pairs = command_for_body_velocity(
            effective.linear_x,
            effective.linear_y,
            effective.angular_z,
            model=self.model,
        )
        return build_motor_frame(pairs)

    def _write(self, frame: bytes) -> bool:
        port = self._port
        if port is None:
            return False
        try:
            port.write(frame)
        except Exception as exc:  # noqa: BLE001 - the port died, say so
            self.stats.frames_failed += 1
            self.stats.last_error = f"{type(exc).__name__}: {exc}"
            self._state = ConnectionState.DISCONNECTED
            return False
        self.stats.frames_sent += 1
        self.stats.last_frame_at = self._clock()
        return True

    def _stream_loop(self) -> None:
        """Send the current command at the frame rate; go quiet when idle.

        While a command is active the frames are streamed continuously, because
        the board's firmware stops the motors when the command stream stops
        (verified on hardware, sesi 2 §9.3).

        When the command ends, a short burst of stop frames is sent and then the
        stream **stops**. The board's watchdog then holds the motors off. This
        matters: continuously streaming zero-speed frames keeps the motor
        driver energised, so the robot hums after every stop -- it was observed
        on the floor, and it is also the behaviour that makes the robot hard to
        push around while the dashboard is open.
        """
        period = 1.0 / self.rate_hz
        next_send = self._clock() + self.settle_s
        stop_frames_left = 0
        while not self._closing.is_set():
            now = self._clock()
            if now < next_send:
                time.sleep(min(next_send - now, period))
                continue
            next_send += period
            command = self.guard.poll()
            if command is None:
                if stop_frames_left > 0:
                    if not self._write(self._stop_frame()):
                        break
                    stop_frames_left -= 1
                else:
                    # Idle: send nothing and let the board's watchdog hold the
                    # motors off.
                    time.sleep(period)
                continue
            stop_frames_left = STOP_FRAME_BURST
            if not self._write(self._frame_for(command)):
                break
        # The stream ended: make sure the board is not left with a live command.
        self._write(self._stop_frame())
