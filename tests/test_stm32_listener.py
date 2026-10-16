"""Unit tests for the read-only STM32 listener (replay mode only, no hardware)."""

from __future__ import annotations

import ast
import struct
from pathlib import Path

import pytest

from amr_core.robot import stm32_listener as L
from amr_core.robot import stm32_protocol as p

LISTENER_SRC = Path(L.__file__)


def _imu_frame(ax: float = 1.0, ay: float = 2.0, az: float = 3.0,
               gx: float = 4.0, gy: float = 5.0, gz: float = 6.0) -> bytes:
    return p.build_frame(p.Stm32Function.IMU, struct.pack("<6f", ax, ay, az, gx, gy, gz))


def _key_frame(key: int = 1, event: int = p.KEY_EVENT_CLICK) -> bytes:
    return p.build_frame(p.Stm32Function.KEY, bytes([key, event]))


def _counter_clock():
    state = {"t": 0.0}

    def clock() -> float:
        state["t"] += 0.1
        return state["t"]

    return clock


# --- replay ----------------------------------------------------------------- #

def test_replay_valid_frames() -> None:
    listener = L.replay_bytes(_imu_frame() + _key_frame())
    assert listener.stats().frames_ok == 2
    assert [r.function_name for r in listener.records()] == ["IMU", "KEY"]
    assert isinstance(listener.records()[0].decoded, p.ImuReading)
    assert listener.records()[0].recognized is True


def test_replay_chunked_matches_whole() -> None:
    data = _imu_frame() + _key_frame() + _imu_frame()
    whole = L.replay_bytes(data)
    chunked = L.replay_bytes(data, chunk_size=3)
    byte_by_byte = L.replay_bytes(data, chunk_size=1)
    assert whole.stats().frames_ok == 3
    assert chunked.stats().frames_ok == 3
    assert byte_by_byte.stats().frames_ok == 3


def test_partial_frame_leaves_pending() -> None:
    frame = _imu_frame()
    listener = L.Stm32Listener()
    listener.feed(frame[:6])
    assert listener.stats().frames_ok == 0
    assert listener.pending  # buffered partial
    listener.feed(frame[6:])
    assert listener.stats().frames_ok == 1


def test_replay_file(tmp_path: Path) -> None:
    path = tmp_path / "capture.bin"
    path.write_bytes(_imu_frame() + _key_frame())
    listener = L.replay_file(path)
    assert listener.stats().frames_ok == 2


# --- errors / noise / unknown ---------------------------------------------- #

def test_crc_error_recorded_and_recovered() -> None:
    bad = bytearray(_imu_frame())
    bad[-1] ^= 0xFF
    listener = L.replay_bytes(bytes(bad) + _key_frame())
    assert listener.stats().crc_errors == 1
    assert listener.stats().frames_ok == 1


def test_noise_resync() -> None:
    listener = L.replay_bytes(b"\x00\x11\x22" + _key_frame())
    assert listener.stats().frames_ok == 1
    assert listener.stats().resyncs >= 1


def test_known_function_unknown_payload_not_forced() -> None:
    # MOTOR (3) is a known function number, but its report format is uncertain.
    listener = L.replay_bytes(p.build_frame(p.Stm32Function.MOTOR, b"\x01\x02\x03"))
    assert listener.stats().frames_ok == 1
    record = listener.records()[0]
    assert record.function_name == "MOTOR"
    assert record.decoded is None
    assert record.recognized is False
    assert listener.stats().unrecognized_frames == 1


def test_unknown_function_number_recorded() -> None:
    listener = L.replay_bytes(p.build_frame(0x7E, b"\x01"))
    record = listener.records()[0]
    assert record.function_name == "UNKNOWN(0x7e)"
    assert record.decoded is None


def test_imu_wrong_length_not_forced() -> None:
    listener = L.replay_bytes(p.build_frame(p.Stm32Function.IMU, b"\x00" * 10))
    assert listener.records()[0].decoded is None
    assert listener.stats().unrecognized_frames == 1


# --- bounds / empty --------------------------------------------------------- #

def test_buffer_is_bounded() -> None:
    listener = L.Stm32Listener(max_buffer_bytes=64)
    listener.feed(b"\xaa" * 2000)
    assert len(listener.pending) <= 64
    assert listener.stats().overflows >= 1


def test_records_are_bounded() -> None:
    listener = L.Stm32Listener(max_records=5)
    for _ in range(20):
        listener.feed(_key_frame())
    assert len(listener.records()) == 5
    assert listener.stats().frames_ok == 20
    assert listener.stats().records_dropped > 0


def test_empty_input_is_safe() -> None:
    listener = L.Stm32Listener()
    assert listener.feed(b"") == []
    assert listener.stats().bytes_in == 0
    assert L.replay_bytes(b"").stats().frames_ok == 0


# --- timestamps / summary --------------------------------------------------- #

def test_timestamps_are_recorded() -> None:
    listener = L.Stm32Listener(clock=_counter_clock())
    listener.feed(_key_frame())
    assert listener.raw_records()[0].timestamp_s == pytest.approx(0.1)
    assert listener.records()[0].timestamp_s == pytest.approx(0.1)


def test_summary_reports_functions_seen() -> None:
    summary = L.replay_bytes(_imu_frame() + _key_frame() + _key_frame()).summary()
    assert summary["frames_ok"] == 3
    assert summary["functions_seen"]["IMU"] == 1
    assert summary["functions_seen"]["KEY"] == 2


# --- no hardware path ------------------------------------------------------- #

def test_listener_module_does_not_import_serial() -> None:
    tree = ast.parse(LISTENER_SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "serial" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "serial"


def test_listener_module_has_no_write_calls() -> None:
    tree = ast.parse(LISTENER_SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "write", "listener must never write bytes"


def test_serial_transport_is_inert() -> None:
    transport = L.SerialTransport("/dev/ttyACM0")
    assert transport.available() is False
    with pytest.raises(L.SerialTransportDisabled):
        transport.open()
    with pytest.raises(L.SerialTransportDisabled):
        transport.read()
