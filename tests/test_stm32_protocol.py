"""Unit tests for the STM32 frame decoder (read-only, no hardware).

The CRC tests compare against an *independent* implementation (a bitwise
reflected CRC-8) and the standard CRC-8/MAXIM check value — not against the
module's own table — so a hand-typed table error would be caught.
"""

from __future__ import annotations

import struct

import pytest

from amr_core.robot import stm32_protocol as p


def _crc8_bitwise(data: bytes) -> int:
    """Independent reference: reflected CRC-8, poly 0x8C, init 0."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc >> 1) ^ p.CRC8_POLY_REFLECTED) & 0xFF if crc & 1 else crc >> 1
    return crc


def _imu_frame(ax: float = 1.0, ay: float = 2.0, az: float = 3.0,
               gx: float = 4.0, gy: float = 5.0, gz: float = 6.0) -> bytes:
    return p.build_frame(p.Stm32Function.IMU, struct.pack("<6f", ax, ay, az, gx, gy, gz))


# --- CRC ------------------------------------------------------------------ #

def test_crc_table_matches_bitwise_reference() -> None:
    derived = tuple(_crc8_bitwise(bytes([i])) for i in range(256))
    assert derived == p.CRC8_TABLE
    assert len(p.CRC8_TABLE) == 256


def test_crc_check_value_is_maxim() -> None:
    assert p.crc8(b"123456789") == 0xA1


def test_crc_empty_is_zero() -> None:
    assert p.crc8(b"") == 0


def test_crc_matches_bitwise_for_samples() -> None:
    for sample in (b"\x00", b"\xff", b"\xaa\x55\x07\x18", bytes(range(40))):
        assert p.crc8(sample) == _crc8_bitwise(sample)


# --- Frame decoding ------------------------------------------------------- #

def test_decodes_valid_frame() -> None:
    dec = p.FrameDecoder()
    frames = dec.feed(_imu_frame())
    assert len(frames) == 1
    assert frames[0].function == p.Stm32Function.IMU
    assert frames[0].payload == struct.pack("<6f", 1, 2, 3, 4, 5, 6)
    assert dec.stats.frames_ok == 1


def test_zero_length_payload_frame() -> None:
    dec = p.FrameDecoder()
    frame = p.build_frame(p.Stm32Function.SYS, b"")
    assert len(frame) == p.MIN_FRAME_BYTES
    frames = dec.feed(frame)
    assert len(frames) == 1
    assert frames[0].payload == b""


def test_multiple_frames_in_one_buffer() -> None:
    dec = p.FrameDecoder()
    data = _imu_frame() + p.build_frame(p.Stm32Function.KEY, b"\x01\x20") + _imu_frame()
    frames = dec.feed(data)
    assert [f.function for f in frames] == [7, 6, 7]


def test_partial_frame_across_calls() -> None:
    dec = p.FrameDecoder()
    frame = _imu_frame()
    assert dec.feed(frame[:5]) == []
    assert dec.pending  # the first 5 bytes are buffered
    frames = dec.feed(frame[5:])
    assert len(frames) == 1


def test_byte_by_byte() -> None:
    dec = p.FrameDecoder()
    out: list[p.Stm32Frame] = []
    for byte in p.build_frame(p.Stm32Function.KEY, b"\x02\x01"):
        out.extend(dec.feed(bytes([byte])))
    assert len(out) == 1
    assert out[0].payload == b"\x02\x01"


def test_noise_before_frame_is_resynced() -> None:
    dec = p.FrameDecoder()
    frames = dec.feed(b"\x11\x22\x33" + _imu_frame())
    assert len(frames) == 1
    assert dec.stats.resyncs >= 1


def test_bad_second_sync_byte_recovers() -> None:
    dec = p.FrameDecoder()
    frames = dec.feed(b"\xaa\x00\xaa\x55" + _imu_frame()[2:])
    assert len(frames) == 1


def test_crc_error_is_dropped_and_recovers() -> None:
    dec = p.FrameDecoder()
    bad = bytearray(_imu_frame())
    bad[-1] ^= 0xFF
    frames = dec.feed(bytes(bad) + _imu_frame())
    assert len(frames) == 1
    assert dec.stats.crc_errors == 1


def test_invalid_length_rejected() -> None:
    dec = p.FrameDecoder(max_payload_len=16)
    frames = dec.feed(p.build_frame(p.Stm32Function.SYS, bytes(32)))
    assert frames == []
    assert dec.stats.length_errors >= 1


def test_recovery_after_corrupt_frame() -> None:
    dec = p.FrameDecoder()
    corrupt = b"\xaa\x55\x07\x18" + bytes(24) + b"\x00"  # valid header, bad CRC
    data = corrupt + _imu_frame() + p.build_frame(p.Stm32Function.KEY, b"\x01\x01")
    frames = dec.feed(data)
    assert [f.function for f in frames] == [7, 6]


def test_buffer_is_bounded() -> None:
    dec = p.FrameDecoder(max_buffer_bytes=64)
    dec.feed(b"\xaa" * 1000)
    assert len(dec.pending) <= 64
    assert dec.stats.overflows >= 1


def test_reset_keeps_counters() -> None:
    dec = p.FrameDecoder()
    dec.feed(_imu_frame())
    dec.reset()
    assert dec.pending == b""
    assert dec.stats.frames_ok == 1


def test_version_dependent_function_still_parsed_raw() -> None:
    # Function 11 is RGB upstream / NONE in the shipped SDK; we do not depend on it.
    dec = p.FrameDecoder()
    frames = dec.feed(p.build_frame(11, b"\x01"))
    assert len(frames) == 1
    assert frames[0].function == 11
    assert p.decode_payload(frames[0]) is None


# --- Payload decoding ----------------------------------------------------- #

def test_decode_imu_round_trip() -> None:
    frame = p.Stm32Frame(
        p.Stm32Function.IMU, struct.pack("<6f", 0.1, -0.2, 0.3, 1.5, -2.5, 3.5), b""
    )
    reading = p.decode_imu(frame.payload)
    assert reading is not None
    assert reading.ax == pytest.approx(0.1)
    assert reading.gz == pytest.approx(3.5)


def test_decode_imu_wrong_length_returns_none() -> None:
    assert p.decode_imu(b"\x00" * 10) is None


def test_decode_battery() -> None:
    assert p.decode_battery(bytes([0x04, 0x04, 0x29])) == p.BatteryReading(raw=0x2904)


def test_decode_battery_other_subtype_returns_none() -> None:
    assert p.decode_battery(bytes([0x01, 0x00, 0x00])) is None
    assert p.decode_battery(b"\x04") is None


def test_decode_button() -> None:
    assert p.decode_button(b"\x02\x20") == p.ButtonEvent(key_id=2, event=p.KEY_EVENT_CLICK)
    assert p.decode_button(b"\x01") is None


def test_decode_payload_dispatch() -> None:
    imu = p.Stm32Frame(p.Stm32Function.IMU, struct.pack("<6f", 1, 2, 3, 4, 5, 6), b"")
    assert isinstance(p.decode_payload(imu), p.ImuReading)
    sys_frame = p.Stm32Frame(p.Stm32Function.SYS, bytes([0x04, 0x00, 0x29]), b"")
    assert isinstance(p.decode_payload(sys_frame), p.BatteryReading)
    key_frame = p.Stm32Frame(p.Stm32Function.KEY, b"\x01\x01", b"")
    assert isinstance(p.decode_payload(key_frame), p.ButtonEvent)


def test_unknown_function_payload_not_decoded() -> None:
    # MOTOR (3) is a known function number, but its report format is uncertain.
    motor = p.Stm32Frame(p.Stm32Function.MOTOR, b"\x01\x02\x03", b"")
    assert p.decode_payload(motor) is None


def test_build_frame_round_trips_through_decoder() -> None:
    for func, payload in ((0, b"\x04\x00\x29"), (6, b"\x01\x20"), (7, bytes(24))):
        dec = p.FrameDecoder()
        frames = dec.feed(p.build_frame(func, payload))
        assert len(frames) == 1
        assert frames[0].function == func
        assert frames[0].payload == payload
