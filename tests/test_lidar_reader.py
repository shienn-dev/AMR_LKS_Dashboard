"""Tests for the background LiDAR reader using an injected fake serial port.

No real hardware and no ``pyserial`` are needed: the reader accepts a
``serial_factory`` and catches ``OSError`` (the base of pyserial's
``SerialException``) so the same code paths are exercised.
"""

from __future__ import annotations

import importlib.util
import time

from amr_core.lidar.config import LidarConfig
from amr_core.lidar.protocol import POINTS_PER_PACKET, build_packet
from amr_core.lidar.reader import LidarReader, LidarStatus


def _packet(distance_mm: int = 100, start_deg: float = 0.0, end_deg: float = 11.0) -> bytes:
    return build_packet(
        speed_dps=3580,
        start_angle_deg=start_deg,
        end_angle_deg=end_deg,
        timestamp_ms=0,
        measurements=[(distance_mm, 5)] * POINTS_PER_PACKET,
    )


class FakeSerial:
    """Returns queued chunks, then empty reads (simulating read timeouts)."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""

    def close(self) -> None:
        self.closed = True


class FailingSerial:
    """Always raises an OSError on read (simulates a disconnected device)."""

    def __init__(self) -> None:
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        raise OSError("device disconnected")

    def close(self) -> None:
        self.closed = True


class FakeClock:
    """Deterministic monotonic clock for rate tests."""

    def __init__(self, step: float = 0.1) -> None:
        self._t = 0.0
        self._step = step

    def __call__(self) -> float:
        self._t += self._step
        return self._t


def _wait(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def _reader(chunks: list[bytes], **config_kwargs) -> LidarReader:
    config = LidarConfig(reconnect_delay_s=0.01, idle_timeout_s=5.0, **config_kwargs)
    return LidarReader(config, serial_factory=lambda port, baud: FakeSerial(chunks))


# --- parsing ---------------------------------------------------------------- #

def test_reader_parses_valid_packets_and_counts_crc_failures() -> None:
    good = _packet()
    corrupt = bytearray(good)
    corrupt[46] ^= 0xFF  # break the CRC only
    stream = b"\x00\x11\x22" + good + bytes(corrupt) + good + good

    reader = _reader([stream])
    assert reader.start()
    assert _wait(lambda: reader.stats().packets_ok >= 3)
    reader.stop()

    stats = reader.stats()
    assert stats.packets_ok == 3
    assert stats.crc_failures >= 1
    assert stats.status is LidarStatus.STOPPED


def test_reader_keeps_partial_packet_in_buffer() -> None:
    good = _packet()
    reader = _reader([good + good[:20]])  # a complete packet + a truncated one
    reader.start()
    assert _wait(lambda: reader.stats().packets_ok >= 1)
    reader.stop()
    assert reader.stats().packets_ok == 1


def test_reader_reassembles_packet_split_across_reads() -> None:
    good = _packet()
    reader = _reader([good[:10], good[10:]])
    reader.start()
    assert _wait(lambda: reader.stats().packets_ok >= 1)
    reader.stop()
    assert reader.stats().packets_ok == 1


def test_reader_accumulates_points_from_many_packets() -> None:
    packets = [
        _packet(start_deg=float((k * 12) % 360), end_deg=float((k * 12 + 11) % 360))
        for k in range(36)
    ]
    reader = _reader([b"".join(packets)])
    reader.start()
    assert _wait(lambda: reader.stats().packets_ok >= 36)
    reader.stop()

    snapshot = reader.snapshot()
    assert snapshot.complete
    assert len(snapshot.points) == 360


def test_reader_reports_packet_rate() -> None:
    good = _packet()
    reader = LidarReader(
        LidarConfig(reconnect_delay_s=0.01, idle_timeout_s=5.0),
        serial_factory=lambda port, baud: FakeSerial([good + good + good]),
        clock=FakeClock(0.1),
    )
    reader.start()
    assert _wait(lambda: reader.stats().packets_ok >= 3)
    reader.stop()
    assert reader.stats().packets_per_s > 0


# --- resilience ------------------------------------------------------------- #

def test_reader_recovers_from_disconnected_device() -> None:
    reader = LidarReader(
        LidarConfig(reconnect_delay_s=0.01, idle_timeout_s=5.0),
        serial_factory=lambda port, baud: FailingSerial(),
    )
    reader.start()
    assert _wait(lambda: reader.stats().reconnects >= 1)
    reader.stop()

    stats = reader.stats()
    assert stats.reconnects >= 1
    assert "disconnected" in stats.last_error
    assert stats.status is LidarStatus.STOPPED


def test_reader_reports_unavailable_without_pyserial(monkeypatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    reader = LidarReader(LidarConfig())
    assert reader.start() is False
    assert reader.stats().status is LidarStatus.UNAVAILABLE


def test_stop_joins_the_thread() -> None:
    reader = _reader([])  # never yields data; stays in the read loop
    assert reader.start()
    assert reader.is_alive
    reader.stop()
    assert not reader.is_alive


def test_start_is_idempotent_while_running() -> None:
    reader = _reader([])
    assert reader.start()
    assert reader.start()  # second call is a no-op, still running
    reader.stop()
