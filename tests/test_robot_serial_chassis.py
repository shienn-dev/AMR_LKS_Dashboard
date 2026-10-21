"""Serial chassis adapter tests (fake port, no hardware).

The adapter is exercised against a fake port that records every byte, so the
tests can check what would actually reach the board: the frame format, the
frame rate, and above all that the robot is told to stop when it has to.
"""

from __future__ import annotations

import struct
import time

from amr_core.robot.interfaces import ChassisCommand, ConnectionState
from amr_core.robot.motion_guard import MotionGuard
from amr_core.robot.safety import SpeedLimits
from amr_core.robot.serial_chassis import SerialChassisAdapter


class FakePort:
    """Records everything that would be written to the board."""

    def __init__(self) -> None:
        self.written: list[bytes] = []
        self.closed = False
        self.flushes = 0

    def write(self, data: bytes, /) -> int:
        self.written.append(bytes(data))
        return len(data)

    def flush(self) -> None:
        self.flushes += 1

    def close(self) -> None:
        self.closed = True


def decode_motor_frame(frame: bytes) -> list[tuple[int, float]]:
    """Decode a func-3 MOTOR frame back into ``(motor_id, rps)`` pairs.

    Layout: ``[0xAA 0x55 0x03 len 0x01 n (id-1, float32 rps) x n] crc``.
    """
    assert frame[0] == 0xAA and frame[1] == 0x55
    assert frame[2] == 3  # MOTOR
    assert frame[4] == 0x01  # motor sub-command
    count = frame[5]
    pairs = []
    offset = 6
    for _ in range(count):
        motor_index = frame[offset]
        (rps,) = struct.unpack_from("<f", frame, offset + 1)
        pairs.append((motor_index + 1, rps))
        offset += 5
    return pairs


def _adapter(port: FakePort, **kwargs) -> SerialChassisAdapter:
    guard = kwargs.pop("guard", None) or MotionGuard()
    return SerialChassisAdapter(
        port="/dev/fake",
        limits=SpeedLimits(max_linear_x=0.19, max_linear_y=0.05, max_angular_z=0.20),
        guard=guard,
        port_factory=lambda name, baud: port,
        rate_hz=kwargs.pop("rate_hz", 200.0),
        settle_s=0.0,
        **kwargs,
    )


def test_open_reports_connected_and_stays_quiet_until_a_command() -> None:
    """An open port with no command sends nothing.

    The board's watchdog holds the motors off when the stream is quiet, which
    is what keeps the robot from humming while it is idle.
    """
    port = FakePort()
    guard = MotionGuard()
    adapter = _adapter(port, guard=guard)
    assert adapter.open() is ConnectionState.CONNECTED
    time.sleep(0.05)
    assert port.written == []
    guard.arm("session-a")
    guard.heartbeat("session-a")
    guard.request_motion("session-a", ChassisCommand(0.19, 0.0, 0.0))
    time.sleep(0.05)
    assert len(port.written) >= 3
    adapter.close()
    assert adapter.state() is ConnectionState.DISABLED


def test_the_stream_carries_the_motor_rates_of_the_guarded_command() -> None:
    port = FakePort()
    guard = MotionGuard()
    adapter = _adapter(port, guard=guard)
    adapter.open()
    guard.arm("session-a")
    guard.heartbeat("session-a")
    assert guard.request_motion("session-a", ChassisCommand(0.19, 0.0, 0.0)) is True
    time.sleep(0.05)
    adapter.close()
    moving = [f for f in port.written if any(abs(r) > 0 for _i, r in decode_motor_frame(f))]
    assert moving, "expected at least one frame with a non-zero motor rate"
    rates = dict(decode_motor_frame(moving[-1]))
    assert rates[1] < 0 and rates[2] < 0
    assert rates[3] > 0 and rates[4] > 0


def test_releasing_the_motion_sends_zero_rates() -> None:
    port = FakePort()
    guard = MotionGuard()
    adapter = _adapter(port, guard=guard)
    adapter.open()
    guard.arm("session-a")
    guard.heartbeat("session-a")
    guard.request_motion("session-a", ChassisCommand(0.19, 0.0, 0.0))
    time.sleep(0.02)
    guard.release_motion("session-a")
    time.sleep(0.02)
    adapter.close()
    stopped = [f for f in port.written if all(r == 0.0 for _i, r in decode_motor_frame(f))]
    assert stopped, "expected a frame with all motor rates zero"


def test_the_stream_goes_quiet_when_idle() -> None:
    """After a stop the adapter must stop sending frames.

    Streaming zero-speed frames keeps the motor driver energised, and the
    robot was observed to hum after every stop because of it. Idle means
    silence: the board's watchdog holds the motors off.
    """
    port = FakePort()
    guard = MotionGuard()
    adapter = _adapter(port, guard=guard)
    adapter.open()
    guard.arm("session-a")
    guard.heartbeat("session-a")
    guard.request_motion("session-a", ChassisCommand(0.19, 0.0, 0.0))
    time.sleep(0.02)
    guard.release_motion("session-a")
    time.sleep(0.05)
    sent_after_stop = len(port.written)
    time.sleep(0.05)
    assert len(port.written) == sent_after_stop, "the stream kept going while idle"
    assert adapter.state() is ConnectionState.CONNECTED, "the port must stay open"
    adapter.close()


def test_close_sends_a_final_stop_frame() -> None:
    port = FakePort()
    adapter = _adapter(port)
    adapter.open()
    time.sleep(0.02)
    adapter.close()
    assert port.closed is True
    assert port.written, "expected the adapter to have written something"
    final = decode_motor_frame(port.written[-1])
    assert [rate for _i, rate in final] == [0.0, 0.0, 0.0, 0.0]


def test_submit_clamps_to_the_limits() -> None:
    port = FakePort()
    guard = MotionGuard()
    adapter = _adapter(port, guard=guard)
    adapter.open()
    guard.arm("session-a")
    guard.heartbeat("session-a")
    outcome = adapter.submit(ChassisCommand(5.0, 5.0, 5.0), session_id="session-a")
    assert outcome.accepted is True
    assert adapter.last_command() == ChassisCommand(0.19, 0.05, 0.20)
    adapter.close()


def test_submit_is_refused_when_the_guard_refuses() -> None:
    port = FakePort()
    guard = MotionGuard()
    adapter = _adapter(port, guard=guard)
    adapter.open()
    outcome = adapter.submit(ChassisCommand(0.1, 0.0, 0.0), session_id="nobody")
    assert outcome.accepted is False
    assert outcome.transmitted is False
    adapter.close()


def test_a_dead_port_is_reported_as_disconnected() -> None:
    class BrokenPort(FakePort):
        def write(self, data: bytes, /) -> int:
            raise OSError("device disconnected")

    port = BrokenPort()
    guard = MotionGuard()
    adapter = _adapter(port, guard=guard)
    adapter.open()
    guard.arm("session-a")
    guard.heartbeat("session-a")
    guard.request_motion("session-a", ChassisCommand(0.19, 0.0, 0.0))
    time.sleep(0.05)
    assert adapter.state() is ConnectionState.DISCONNECTED
    assert "device disconnected" in adapter.stats.last_error
    adapter.close()


def test_opening_without_a_port_factory_is_unavailable() -> None:
    adapter = SerialChassisAdapter(port="/dev/fake")
    assert adapter.open() is ConnectionState.UNAVAILABLE
    assert "port factory" in adapter.stats.last_error


def test_the_stream_never_exceeds_the_tested_rate() -> None:
    port = FakePort()
    guard = MotionGuard()
    adapter = _adapter(port, guard=guard)
    adapter.open()
    guard.arm("session-a")
    guard.heartbeat("session-a")
    guard.request_motion("session-a", ChassisCommand(0.19, 0.19, 0.0))
    time.sleep(0.03)
    adapter.close()
    for frame in port.written:
        for _motor_id, rate in decode_motor_frame(frame):
            assert abs(rate) <= 1.0 + 1e-6
